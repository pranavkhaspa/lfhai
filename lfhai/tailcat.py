"""Tailcat networking layer for lfhai.

Wraps the tailcat binary (https://github.com/tailscale/tailcat) to provide
encrypted tunnels between nodes without requiring Tailscale accounts.

Verified against the real `tailcat serve --json`, `tailcat ping` and
`tailcat forward` subcommands.

Usage::

    # Server side (controller):
    server = TailcatServer()
    await server.start()
    print(server.address)  # Share this address with workers

    # Client side (worker):
    client = TailcatClient(server_address)
    connected = await client.connect()  # tailcat ping
    tunnel = await client.forward_port(8001, 8001)  # port forward
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil

logger = logging.getLogger("lfhai.tailcat")


class TailcatError(Exception):
    """Raised when tailcat operations fail."""


def find_tailcat() -> str | None:
    """Find the tailcat binary on PATH."""
    return shutil.which("tailcat")


def ensure_tailcat() -> str:
    """Ensure tailcat is available, raise if not found."""
    path = find_tailcat()
    if not path:
        raise TailcatError(
            "tailcat not found. Install it:\n"
            "  brew install tailcat          # macOS\n"
            "  go install github.com/tailscale/tailcat/cmd/tailcat@latest\n"
            "  # or download from https://github.com/tailscale/tailcat/releases"
        )
    return path


class TailcatServer:
    """A tailcat listener that accepts connections from workers.

    Uses ``tailcat serve --json [ports...]`` which writes
    ``{"listenAddr": "tc..."}`` to stdout before accepting connections.
    """

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._address: str = ""

    @property
    def address(self) -> str:
        return self._address

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self, port: int = 0) -> str:
        """Start a tailcat server and return the ``tc...`` connection address.

        Args:
            port: Port to serve on. 0 = accept a single connection on any
                  port (pipe to stdout).
        """
        binary = ensure_tailcat()
        cmd = [binary, "serve", "--json"]
        if port:
            cmd.append(str(port))

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # The --json flag writes a single JSON object to stdout, then blocks.
        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            if self._process.stdout:
                try:
                    line = await asyncio.wait_for(self._process.stdout.readline(), timeout=2)
                except asyncio.TimeoutError:
                    pass
                else:
                    if line:
                        try:
                            data = json.loads(line.decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass
                        else:
                            addr = data.get("listenAddr", "")
                            if addr.startswith("tc"):
                                self._address = addr
                                logger.info("Tailcat server listening: %s", self._address)
                                return self._address

            if self._process.returncode is not None:
                stderr = b""
                if self._process.stderr:
                    stderr = await self._process.stderr.read()
                raise TailcatError(
                    f"Failed to start tailcat server or get address: "
                    f"exited with code {self._process.returncode}: "
                    f"{stderr.decode(errors='replace')}"
                )
            await asyncio.sleep(0.1)

        # Cleanup on timeout
        self.stop()
        raise TailcatError("Failed to start tailcat server or get address")

    def stop(self):
        """Stop the tailcat server."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
        self._process = None
        self._address = ""

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        self.stop()


class TailcatClient:
    """A tailcat client that connects to a server's tunnel.

    Uses ``tailcat ping <address>`` for connectivity checks and
    ``tailcat forward <address> <local>:<remote>`` for port forwarding.
    """

    def __init__(self, server_address: str) -> None:
        self._address = server_address
        self._process: asyncio.subprocess.Process | None = None

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def connect(self, timeout: float = 15) -> bool:
        """Connect to the tailcat server.

        Runs ``tailcat ping <address>`` (non-blocking, exits with 0 on
        success).
        """
        binary = ensure_tailcat()
        cmd = [binary, "ping", self._address]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            if proc.returncode == 0:
                logger.info("Connected to tailcat server: %s", self._address)
                return True
            stderr = b""
            if proc.stderr:
                stderr = await proc.stderr.read()
            logger.warning(
                "Tailcat ping failed (rc=%d): %s", proc.returncode,
                stderr.decode(errors="replace"),
            )
            return False
        except asyncio.TimeoutError:
            logger.warning("Tailcat connection timed out")
            return False

    async def forward_port(
        self, local_port: int, remote_port: int
    ) -> asyncio.subprocess.Process | None:
        """Forward a local port to the remote server through tailcat."""
        binary = ensure_tailcat()
        cmd = [binary, "forward", self._address, f"{local_port}:{remote_port}"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            logger.info("Forwarding local:%d -> remote:%d via tailcat", local_port, remote_port)
            return process
        except Exception as e:
            logger.error("Failed to start port forwarding: %s", e)
            return None

    def disconnect(self):
        """Disconnect from the server."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
        self._process = None


class TailcatTunnel:
    """High-level tunnel manager for lfhai node communication.

    Provides a simple interface to set up encrypted tunnels between
    the controller and worker nodes.
    """

    def __init__(self, role: str = "server") -> None:
        """
        Args:
            role: "server" for controller, "client" for workers
        """
        self.role = role
        self._server: TailcatServer | None = None
        self._client: TailcatClient | None = None

    async def setup_server(self, port: int = 0) -> str:
        """Start a tailcat server (for the controller).

        Returns the address that workers should use to connect.
        """
        self._server = TailcatServer()
        address = await self._server.start(port)
        logger.info("Tunnel server ready: %s", address)
        return address

    async def setup_client(self, server_address: str) -> bool:
        """Connect to a tailcat server (for workers).

        Args:
            server_address: The tc... address from the controller.

        Returns True if connected successfully.
        """
        self._client = TailcatClient(server_address)
        return await self._client.connect()

    async def forward(self, local_port: int, remote_port: int):
        """Forward a local port through the tunnel."""
        if not self._client:
            raise TailcatError("No client connected. Call setup_client first.")
        return await self._client.forward_port(local_port, remote_port)

    def shutdown(self):
        """Clean up all tunnel resources."""
        if self._server:
            self._server.stop()
        if self._client:
            self._client.disconnect()
