"""CLI tool for managing lfhai cluster."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import httpx


def _default_db_path() -> str:
    return "lfhai.db"


@click.group()
@click.option("--controller", "-c", default="http://localhost:8001", help="Controller URL")
@click.option("--gateway", "-g", default="http://localhost:8000", help="Gateway URL")
@click.pass_context
def main(ctx, controller, gateway):
    """lfh - Local-First Heterogeneous AI Runtime CLI"""
    ctx.ensure_object(dict)
    ctx.obj["controller"] = controller
    ctx.obj["gateway"] = gateway


@main.command()
@click.pass_context
def status(ctx):
    """Show cluster status."""
    ctrl = ctx.obj["controller"]
    gw = ctx.obj["gateway"]

    # Check gateway
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{gw}/health")
            gw_data = resp.json()
            click.echo(f"Gateway:     {click.style(gw_data['status'], fg='green')}")
            click.echo(f"  Controller: {gw_data.get('controller', 'unknown')}")
    except Exception:
        click.echo(f"Gateway:     {click.style('unreachable', fg='red')}")

    # Check controller
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{ctrl}/health")
            click.echo(f"Controller:  {click.style('ok', fg='green')}")
    except Exception:
        click.echo(f"Controller:  {click.style('unreachable', fg='red')}")
        return

    # List nodes
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{ctrl}/api/v1/nodes")
            nodes = resp.json()
            click.echo(f"\nNodes ({len(nodes)}):")
            for n in nodes:
                status_color = "green" if n["status"] == "online" else "red"
                hostname = n.get("hostname", "unknown")
                gpu = n.get("resources", {}).get("gpu")
                gpu_info = f" [{gpu.get('model', '')}]" if gpu and gpu.get("model") else ""
                caps = n.get("capabilities", {}).get("models", [])
                models_info = f" models={caps}" if caps else ""
                click.echo(
                    f"  {n['node_id'][:12]}  "
                    f"{click.style(n['status'], fg=status_color)}  "
                    f"{hostname}{gpu_info}{models_info}"
                )
    except Exception as e:
        click.echo(f"Error listing nodes: {e}")


@main.command()
@click.pass_context
def nodes(ctx):
    """List all registered nodes."""
    ctrl = ctx.obj["controller"]
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{ctrl}/api/v1/nodes")
            nodes = resp.json()
            if not nodes:
                click.echo("No nodes registered.")
                return
            click.echo(json.dumps(nodes, indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("model", default="llama3")
@click.argument("prompt")
@click.option("--stream", is_flag=True, help="Stream the response")
@click.pass_context
def chat(ctx, model, prompt, stream):
    """Submit a chat request to the cluster.

    Example: lfh chat llama3 "What is the capital of France?"
    """
    gw = ctx.obj["gateway"]

    messages = [{"role": "user", "content": prompt}]
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }

    try:
        with httpx.Client(timeout=300) as client:
            if stream:
                with client.stream("POST", f"{gw}/v1/chat/completions", json=payload) as resp:
                    if resp.status_code != 200:
                        click.echo(f"Error: {resp.text}", err=True)
                        sys.exit(1)
                    for line in resp.iter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                click.echo()
                                break
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            click.echo(content, nl=False)
            else:
                resp = client.post(f"{gw}/v1/chat/completions", json=payload)
                if resp.status_code != 200:
                    click.echo(f"Error: {resp.text}", err=True)
                    sys.exit(1)
                result = resp.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                click.echo(content)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.pass_context
def models(ctx):
    """List all available models across the cluster."""
    gw = ctx.obj["gateway"]
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{gw}/v1/models")
            data = resp.json()
            model_list = data.get("data", [])
            if not model_list:
                click.echo("No models available. Start a worker with Ollama models.")
                return
            for m in model_list:
                click.echo(f"  {m['id']}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.group()
def worker():
    """Worker management commands."""
    pass


@worker.command("start")
@click.option("--controller-url", "-c", default="http://localhost:8001", help="Controller URL")
@click.option("--port", "-p", default=8002, help="Worker HTTP port")
@click.option("--ollama-url", "-o", default="http://localhost:11434", help="Ollama API URL")
@click.option("--credentials", "-cr", default=None, help="Credential file path")
def worker_start(controller_url, port, ollama_url, credentials):
    """Start a worker daemon on this machine."""
    from lfhai.worker import run_worker
    run_worker(
        ctrl_url=controller_url,
        worker_port=port,
        ollama=ollama_url,
        credentials=credentials,
    )


@worker.command("status")
@click.option("--url", "-u", default="http://localhost:8002", help="Worker URL")
def worker_status(url):
    """Check worker status."""
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{url}/worker/status")
            data = resp.json()
            click.echo(f"Node ID:  {data.get('node_id', 'unknown')}")
            click.echo(f"Status:   {data.get('status', 'unknown')}")
            click.echo(f"Ollama:   {data.get('ollama_url', 'unknown')}")
            models = data.get("models", [])
            click.echo(f"Models:   {', '.join(models) if models else 'none detected'}")
    except Exception as e:
        click.echo(f"Worker unreachable: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--db", default="lfhai.db", show_default=True, help="Controller database file")
@click.pass_context
def controller_cmd(ctx, db):
    """Start the controller."""
    from lfhai.controller import run_controller
    run_controller(db_path=db)


@main.command()
@click.pass_context
def gateway_cmd(ctx):
    """Start the gateway."""
    from lfhai.gateway import run_gateway
    run_gateway()


@main.group()
def node():
    """Node management commands."""
    pass


@node.command("join")
@click.argument("token")
@click.option("--credentials", "-cr", default=None, help="Credential file path")
@click.option("--ollama-url", "-o", default="http://localhost:11434", help="Ollama API URL")
def node_join(token, credentials, ollama_url):
    """Join this machine to a cluster using a join token.

    The token carries the controller address and secret, so no IP finding is
    needed. Generate a token on the controller machine with: lfh token create
    """
    from lfhai.models import NodeCapabilities, NodeInfo
    from lfhai.worker import _get_system_resources

    host, port, secret = _parse_join_token(token)
    if not host:
        click.echo("Invalid token. Expected format: HOST:PORT:SECRET", err=True)
        sys.exit(1)

    controller = f"http://{host}:{port}"

    # Detect hardware; models are re-detected by the worker on start.
    resources = _get_system_resources()
    models = _detect_models_sync(ollama_url)

    capabilities = NodeCapabilities(
        models=models,
        has_gpu=resources.gpu is not None,
    )
    node = NodeInfo(
        hostname=resources.hostname,
        resources=resources,
        capabilities=capabilities,
    )

    payload = {"token": secret, "node": node.model_dump()}
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(f"{controller}/api/v1/nodes/join", json=payload)
            if resp.status_code != 200:
                click.echo(
                    f"Join failed ({resp.status_code}): "
                    f"{resp.json().get('detail', resp.text)}",
                    err=True,
                )
                sys.exit(1)
            data = resp.json()
    except httpx.HTTPError as e:
        click.echo(f"Could not reach controller at {controller}: {e}", err=True)
        sys.exit(1)

    from lfhai.credentials import save_credentials
    creds_path = Path(credentials) if credentials else None
    path = save_credentials(controller, data["node_id"], data["node_secret"], creds_path)
    click.echo(click.style("Joined cluster.", fg="green"))
    click.echo(f"  Node ID:     {data['node_id']}")
    click.echo(f"  Controller:  {controller}")
    click.echo(f"  Credentials: {path}")
    click.echo("Start the worker with: lfh worker start")


@main.group()
@click.option("--db", default="lfhai.db", show_default=True, help="Controller database file")
@click.pass_context
def token(ctx, db):
    """Manage cluster join tokens (run on the controller machine)."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


@token.command("create")
@click.option("--ttl-hours", default=1.0, show_default=True, help="Token lifetime in hours")
@click.option("--host", "advertise_host", default=None, help="Advertised controller address")
@click.pass_context
def token_create(ctx, ttl_hours, advertise_host):
    """Mint a join token and print the command to run on a new machine."""
    import asyncio as _asyncio

    from lfhai.registry import NodeRegistry

    async def _create():
        reg = NodeRegistry(ctx.obj["db"])
        await reg.init()
        try:
            token_id, raw_secret, _ = await reg.create_join_token(ttl_hours * 3600)
            return token_id, raw_secret
        finally:
            await reg.close()

    token_id, raw_secret = _asyncio.run(_create())

    host = advertise_host or _detect_advertised_host()
    click.echo(f"Join token {click.style(token_id, bold=True)} created "
               f"(expires in {ttl_hours:g} hour(s))")
    click.echo()
    click.echo("On each machine that should join, run:")
    click.echo()
    click.echo(click.style(f"  lfh node join {host}:8001:{raw_secret}", fg="green", bold=True))
    click.echo()


@token.command("list")
@click.pass_context
def token_list(ctx):
    """List all join tokens and their status."""
    import asyncio as _asyncio

    from lfhai.registry import NodeRegistry

    async def _list():
        reg = NodeRegistry(ctx.obj["db"])
        await reg.init()
        try:
            return await reg.list_join_tokens()
        finally:
            await reg.close()

    tokens = _asyncio.run(_list())
    if not tokens:
        click.echo("No join tokens. Create one with: lfh token create")
        return

    click.echo(f"{'ID':<12} {'Status':<10} {'Node':<28} Expires")
    for t in tokens:
        if t["used_at"]:
            status = "used"
        elif t["expires_at"] < _now():
            status = "expired"
        else:
            status = "active"
        node = t["node_hostname"] or t["node_id"]
        expires = _fmt_time(t["expires_at"])
        click.echo(f"{t['token_id']:<12} {status:<10} {node:<28} {expires}")


@token.command("revoke")
@click.argument("token_id")
@click.pass_context
def token_revoke(ctx, token_id):
    """Revoke a join token."""
    import asyncio as _asyncio

    from lfhai.registry import NodeRegistry

    async def _revoke():
        reg = NodeRegistry(ctx.obj["db"])
        await reg.init()
        try:
            return await reg.revoke_join_token(token_id)
        finally:
            await reg.close()

    ok = _asyncio.run(_revoke())
    if ok:
        click.echo(f"Revoked token {token_id}")
    else:
        click.echo(f"Token {token_id} not found", err=True)
        sys.exit(1)


def _parse_join_token(token: str) -> tuple[str | None, str | None, str | None]:
    """Split TOKEN into (host, port, secret). Accepts an optional scheme prefix."""
    token = token.strip()
    if "://" in token:
        token = token.split("://", 1)[1]
    parts = token.rsplit(":", 2)
    if len(parts) != 3:
        return None, None, None
    host, port, secret = parts
    if not host or not port.isdigit() or not secret:
        return None, None, None
    return host, port, secret


def _detect_models_sync(ollama_url: str) -> list[str]:
    """Best-effort model list from Ollama (worker re-detects on start)."""
    try:
        with httpx.Client(timeout=3) as client:
            resp = client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def _detect_advertised_host() -> str:
    """Best-effort local IP so the token carries the reachable controller address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def _now() -> float:
    import time
    return time.time()


def _fmt_time(ts: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


# Aliases for the group commands
main.add_command(controller_cmd, name="controller")
main.add_command(gateway_cmd, name="gateway")


if __name__ == "__main__":
    main()
