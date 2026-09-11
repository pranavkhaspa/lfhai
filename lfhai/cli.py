"""CLI tool for managing lfhai cluster."""

from __future__ import annotations

import json
import sys

import click
import httpx


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
def worker_start(controller_url, port, ollama_url):
    """Start a worker daemon on this machine."""
    from lfhai.worker import run_worker
    run_worker(ctrl_url=controller_url, worker_port=port, ollama=ollama_url)


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
@click.pass_context
def controller_cmd(ctx):
    """Start the controller."""
    from lfhai.controller import run_controller
    run_controller()


@main.command()
@click.pass_context
def gateway_cmd(ctx):
    """Start the gateway."""
    from lfhai.gateway import run_gateway
    run_gateway()


# Aliases for the group commands
main.add_command(controller_cmd, name="controller")
main.add_command(gateway_cmd, name="gateway")


if __name__ == "__main__":
    main()
