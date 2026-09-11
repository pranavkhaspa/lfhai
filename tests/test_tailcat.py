"""Tests for the tailcat wrapper.

Uses a fake binary (a small Python script) to exercise the server/client
lifecycle, address parsing, and error handling without the real tailcat.
An optional integration test runs ``tailcat serve --json`` / ``tailcat ping``
if the real binary is on PATH.
"""

import asyncio
import os
import textwrap

import pytest

from lfhai.tailcat import (
    TailcatClient,
    TailcatError,
    TailcatServer,
    find_tailcat,
)

# ---------------------------------------------------------------------------
# Fake tailcat binary helpers
# ---------------------------------------------------------------------------

_FAKE_BIN = "/tmp/opencode/fake_tailcat.py"


def _make_fake_tailcat(tmp_path, *, fail: bool = False, bad_json: bool = False):
    """Create a fake ``tailcat`` binary that mimics the real interface."""
    fake_addr = "tcaddr1234567890abcdef"
    code = textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import sys, json
        if len(sys.argv) < 2:
            print("Usage: tailcat <subcommand>", file=sys.stderr); sys.exit(1)
        sub = sys.argv[1]
        if sub == "serve":
            if "--json" not in sys.argv:
                sys.exit(1)
            if {bad_json!r}:
                print("not json garbage")
                sys.exit(0)
            if {fail!r}:
                print("server failed: port in use", file=sys.stderr); sys.exit(1)
            print(json.dumps({{"listenAddr": "{fake_addr}"}}))
            sys.stdout.flush()
            # Block until killed
            import time; time.sleep(300)
        elif sub == "ping":
            if {fail!r}:
                print("unreachable", file=sys.stderr); sys.exit(1)
            print("ok")
            sys.exit(0)
        elif sub == "forward":
            # block until killed
            import time; time.sleep(300)
        else:
            print(f"unknown subcommand: {{sub}}", file=sys.stderr); sys.exit(1)
    """)
    fake = tmp_path / "fake_tailcat"
    fake.write_text(code)
    fake.chmod(0o755)
    return str(fake), fake_addr


@pytest.fixture
def fake_tailcat_env(tmp_path, monkeypatch):
    """Put a fake tailcat binary on PATH and patch find_tailcat."""
    bin_path, addr = _make_fake_tailcat(tmp_path)
    monkeypatch.setenv("PATH", os.path.dirname(bin_path) + ":" + os.environ.get("PATH", ""))
    # find_tailcat uses shutil.which, which reads PATH
    monkeypatch.setattr("lfhai.tailcat.find_tailcat", lambda: bin_path)
    monkeypatch.setattr("lfhai.tailcat.ensure_tailcat", lambda: bin_path)
    return bin_path, addr


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_server_starts_and_returns_address(fake_tailcat_env):
    srv = TailcatServer()
    addr = await srv.start()
    assert addr.startswith("tc")
    assert srv.is_running
    srv.stop()
    assert not srv.is_running


@pytest.mark.asyncio
async def test_server_exit_raises_on_fail(tmp_path, monkeypatch):
    bin_path, _ = _make_fake_tailcat(tmp_path, fail=True)
    monkeypatch.setattr("lfhai.tailcat.ensure_tailcat", lambda: bin_path)
    srv = TailcatServer()
    with pytest.raises(TailcatError, match="Failed to start"):
        await srv.start()


@pytest.mark.asyncio
async def test_server_bad_json_exits(tmp_path, monkeypatch):
    bin_path, _ = _make_fake_tailcat(tmp_path, bad_json=True)
    monkeypatch.setattr("lfhai.tailcat.ensure_tailcat", lambda: bin_path)
    srv = TailcatServer()
    with pytest.raises(TailcatError, match="Failed to start"):
        await srv.start()


@pytest.mark.asyncio
async def test_client_connect_success(fake_tailcat_env):
    cli = TailcatClient("tcaddr")
    ok = await cli.connect()
    assert ok is True


@pytest.mark.asyncio
async def test_client_connect_failure(tmp_path, monkeypatch):
    bin_path, _ = _make_fake_tailcat(tmp_path, fail=True)
    monkeypatch.setattr("lfhai.tailcat.ensure_tailcat", lambda: bin_path)
    cli = TailcatClient("tcaddr")
    ok = await cli.connect()
    assert ok is False


@pytest.mark.asyncio
async def test_forward_port_returns_process(fake_tailcat_env):
    cli = TailcatClient("tcaddr1234567890abcdef")
    proc = await cli.forward_port(9000, 8000)
    assert proc is not None
    assert proc.returncode is None  # still running
    proc.terminate()
    await proc.wait()


@pytest.mark.asyncio
async def test_context_manager(fake_tailcat_env):
    async with TailcatServer() as srv:
        assert srv.address.startswith("tc")
    assert not srv.is_running


# ---------------------------------------------------------------------------
# Integration test — only runs if real tailcat binary is on PATH
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not find_tailcat(), reason="tailcat binary not installed (go install .../tailcat@latest)"
)
@pytest.mark.asyncio
async def test_real_tailcat_server_start_stop():
    """Verify real tailcat serve --json produces a tc... address and exits on stop."""
    srv = TailcatServer()
    addr = await srv.start()
    assert addr.startswith("tc"), f"unexpected address: {addr}"
    assert srv.is_running
    srv.stop()
    # Give the process a moment to die
    await asyncio.sleep(0.2)
    assert not srv.is_running


@pytest.mark.skipif(
    not find_tailcat(), reason="tailcat binary not installed"
)
@pytest.mark.asyncio
async def test_real_tailcat_ping():
    """Start a real server, ping it, then stop."""
    srv = TailcatServer()
    addr = await srv.start()
    try:
        cli = TailcatClient(addr)
        ok = await cli.connect(timeout=10)
        assert ok, "tailcat ping to own server failed"
    finally:
        srv.stop()
        await asyncio.sleep(0.2)
