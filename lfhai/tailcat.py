"""Tailcat networking layer for lfhai.

Wraps the tailcat binary to provide encrypted tunnels between nodes
without requiring Tailscale accounts.

Usage:
    # Server side (controller):
    server = TailcatServer()
    await server.start()
    print(server.address)  # Share this address with workers

    # Client side (worker):
    client = TailcatClient(server_address)
    await client.connect()
    # Now communicate through the tunnel
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess

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
    """A tailcat listener that accepts connections from workers."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._address: str = ""
        self._port: int = 0

    @property
    def address(self) -> str:
        return self._address

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    async def start(self, port: int = 0) -> str:
        """Start a tailcat server and return the connection address.

        Args:
            port: Port to serve on. 0 = random available port.
        """
        binary = ensure_tailcat()
        cmd = [binary, "serve", str(port)] if port else [binary, "serve"]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Read the address from stderr (tailcat prints it there)
        # We need to read a few lines to get the address
        import time

        deadline = time.time() + 10  # 10 second timeout
        while time.time() < deadline:
            if self._process.stderr:
                line = self._process.stderr.readline()
                if "address:" in line.lower() or "listening" in line.lower():
                    # Extract the tc... address
                    for word in line.split():
                        if word.startswith("tc"):
                            self._address = word.strip()
                            logger.info("Tailcat server listening: %s", self._address)
                            return self._address
            if self._process.poll() is not None:
                break
            await asyncio.sleep(0.1)

        raise TailcatError("Failed to start tailcat server or get address")

    def stop(self):
        """Stop the tailcat server."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            self._address = ""

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        self.stop()


class TailcatClient:
    """A tailcat client that connects to a server's tunnel."""

    def __init__(self, server_address: str) -> None:
        self._address = server_address
        self._process: subprocess.Popen | None = None

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.poll() is None

    async def connect(self) -> bool:
        """Connect to the tailcat server.

        Returns True if connection was established.
        """
        binary = ensure_tailcat()
        cmd = [binary, "ping", self._address]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                logger.info("Connected to tailcat server: %s", self._address)
                return True
            else:
                logger.warning("Tailcat ping failed: %s", result.stderr)
                return False
        except subprocess.TimeoutExpired:
            logger.warning("Tailcat connection timed out")
            return False

    async def forward_port(self, local_port: int, remote_port: int) -> subprocess.Popen | None:
        """Forward a local port to the remote server through tailcat."""
        binary = ensure_tailcat()
        cmd = [
            binary, "forward",
            self._address,
            f"{local_port}:{remote_port}",
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info("Forwarding local:%d -> remote:%d via tailcat", local_port, remote_port)
            return process
        except Exception as e:
            logger.error("Failed to start port forwarding: %s", e)
            return None

    def disconnect(self):
        """Disconnect from the server."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
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
