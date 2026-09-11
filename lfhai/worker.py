"""Worker daemon - runs on each node, executes inference tasks via Ollama."""

from __future__ import annotations

import asyncio
import logging
import platform

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from lfhai.models import (
    GPUInfo,
    Heartbeat,
    HeartbeatMetrics,
    NodeCapabilities,
    NodeInfo,
    NodeResources,
)
from lfhai.ollama import OllamaClient

logger = logging.getLogger("lfhai.worker")

app = FastAPI(title="lfhai Worker", version="0.1.0")

# Config - set at startup
controller_url: str = "http://localhost:8001"
node_id: str = ""
node_secret: str = ""
heartbeat_interval: float = 3.0
ollama_url: str = "http://localhost:11434"
ollama_client: OllamaClient | None = None


def _verify_worker_auth(authorization: str | None) -> bool:
    """Return True if the Authorization header matches the local node secret."""
    import hmac
    if not node_secret:
        return False
    expected = f"Bearer {node_secret}"
    return hmac.compare_digest(authorization or "", expected)


def _get_local_ip() -> str:
    """Best-effort local IP detection."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_system_resources() -> NodeResources:
    """Detect local hardware capabilities."""
    import psutil

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    gpu = None
    gpu_model = ""
    gpu_vram = 0
    cuda_version = ""

    # Try to detect NVIDIA GPU via nvidia-smi
    try:
        import subprocess
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            gpu_model = parts[0].strip()
            gpu_vram = int(float(parts[1].strip())) * 1024 * 1024  # MiB to bytes
            cuda_version = parts[2].strip() if len(parts) > 2 else ""
            gpu = GPUInfo(
                model=gpu_model,
                vram_total_bytes=gpu_vram,
                cuda_version=cuda_version,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return NodeResources(
        hostname=platform.node(),
        ip=_get_local_ip(),
        cores=psutil.cpu_count() or 1,
        memory_total_bytes=mem.total,
        memory_used_bytes=mem.used,
        disk_free_bytes=disk.free,
        gpu=gpu,
    )


async def detect_models() -> list[str]:
    """Query Ollama for locally available models."""
    if not ollama_client:
        return []
    try:
        return await ollama_client.get_model_names()
    except Exception as e:
        logger.warning("Failed to detect models: %s", e)
        return []


async def register_with_controller(node_info: NodeInfo) -> bool:
    """Register this worker with the controller."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{controller_url}/api/v1/nodes/register",
                json=node_info.model_dump(),
                headers={"Authorization": f"Bearer {node_secret}"},
            )
            resp.raise_for_status()
            logger.info("Registered with controller as %s", node_info.node_id)
            return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.warning(
                "Not authorized by controller. Run: lfh node join <token> using a "
                "token from: lfh token create"
            )
        else:
            logger.warning("Failed to register with controller: %s", e)
        return False
    except Exception as e:
        logger.warning("Failed to register with controller: %s", e)
        return False


async def send_heartbeat(node_id: str, resources: NodeResources):
    """Send heartbeat to controller with current metrics."""
    import psutil

    metrics = HeartbeatMetrics(
        cpu_usage_pct=psutil.cpu_percent(interval=0.1),
        memory_used_bytes=psutil.virtual_memory().used,
        memory_total_bytes=psutil.virtual_memory().total,
        disk_free_bytes=psutil.disk_usage("/").free,
    )

    # GPU metrics via nvidia-smi
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            metrics.gpu_usage_pct = float(parts[0].strip())
            metrics.gpu_vram_used_bytes = int(float(parts[1].strip())) * 1024 * 1024
            metrics.gpu_temp_celsius = float(parts[2].strip())
    except Exception:
        pass

    hb = Heartbeat(node_id=node_id, metrics=metrics)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{controller_url}/api/v1/nodes/heartbeat",
                json=hb.model_dump(),
                headers={"Authorization": f"Bearer {node_secret}"},
            )
    except Exception as e:
        logger.warning("Heartbeat failed: %s", e)


async def heartbeat_loop(node_id: str, resources: NodeResources):
    """Continuously send heartbeats."""
    while True:
        await send_heartbeat(node_id, resources)
        await asyncio.sleep(heartbeat_interval)


# --- Worker HTTP Endpoints ---

@app.get("/worker/status")
async def worker_status() -> dict:
    models = await detect_models()
    return {
        "node_id": node_id,
        "status": "online",
        "models": models,
        "ollama_url": ollama_url,
    }


@app.post("/worker/task")
async def execute_task(task: dict, request: Request) -> dict:
    """Execute an inference task via Ollama and return the result."""
    if not _verify_worker_auth(request.headers.get("authorization")):
        raise HTTPException(status_code=401, detail="Not authorized")
    model = task.get("model", "llama3")
    messages = task.get("messages", [])
    temperature = task.get("temperature", 0.7)
    stream = task.get("stream", False)

    if not ollama_client:
        raise HTTPException(status_code=503, detail="Ollama client not initialized")

    try:
        if stream:
            import json

            async def stream_result():
                # Translate Ollama's native chunk format into an
                # OpenAI-compatible SSE stream so every upstream proxy
                # (controller, gateway) stays transparent.
                async for chunk in ollama_client._stream_chat({
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": temperature},
                }):
                    delta = (chunk.get("message") or {}).get("content", "")
                    if not delta:
                        # Skip metadata-only events (e.g. {"done": true})
                        continue
                    event = {
                        "id": task.get("task_id", ""),
                        "object": "chat.completion.chunk",
                        "model": chunk.get("model", model),
                        "choices": [
                            {"index": 0, "delta": {"content": delta}, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(event)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(stream_result(), media_type="text/event-stream")
        else:
            result = await ollama_client.generate(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/worker/cancel/{task_id}")
async def cancel_task(task_id: str, request: Request) -> dict:
    if not _verify_worker_auth(request.headers.get("authorization")):
        raise HTTPException(status_code=401, detail="Not authorized")
    # V1: no cancellation support, just acknowledge
    return {"status": "not_supported", "task_id": task_id}


@app.get("/health")
async def health() -> dict:
    ollama_ok = await ollama_client.health_check() if ollama_client else False
    return {"status": "ok", "ollama": ollama_ok}


def run_worker(
    ctrl_url: str = "http://localhost:8001",
    worker_port: int = 8002,
    ollama: str = "http://localhost:11434",
    credentials: str | None = None,
    advertise_ip: str | None = None,
):
    global controller_url, node_id, node_secret, ollama_client, ollama_url

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    controller_url = ctrl_url
    ollama_url = ollama
    ollama_client = OllamaClient(base_url=ollama)

    # Load node credentials from a prior `lfh node join`.
    from pathlib import Path

    from lfhai.credentials import load_credentials

    creds_path = Path(credentials) if credentials else None
    creds = load_credentials(creds_path)
    if creds:
        node_id = creds["node_id"]
        node_secret = creds["node_secret"]
        logger.info("Using node identity: %s", node_id)
    else:
        node_id = ""
        node_secret = ""
        logger.warning(
            "No credentials found. Run: lfh node join <token> (token from: lfh token create)"
        )

    async def _amain() -> None:
        # Detect hardware
        resources = _get_system_resources()
        if advertise_ip:
            resources = resources.model_copy(update={"ip": advertise_ip})
        models = await detect_models()

        capabilities = NodeCapabilities(
            models=models,
            has_gpu=resources.gpu is not None,
            has_cuda=resources.gpu is not None and bool(resources.gpu.cuda_version),
        )

        node_info = NodeInfo(
            node_id=node_id,
            hostname=resources.hostname,
            resources=resources,
            capabilities=capabilities,
            api_port=worker_port,
        )

        logger.info("Worker starting on %s:%d", resources.ip, worker_port)
        logger.info("Hardware: %d cores, %d GB RAM, GPU: %s",
                    resources.cores,
                    resources.memory_total_bytes // (1024**3),
                    resources.gpu.model if resources.gpu else "none")
        logger.info("Models: %s", models)

        # Register with controller (retry loop)
        while True:
            ok = await register_with_controller(node_info)
            if ok:
                break
            logger.info("Retrying registration in 5s...")
            await asyncio.sleep(5)

        # Start heartbeat in background, then serve requests on the same loop
        heartbeat_task = asyncio.create_task(heartbeat_loop(node_id, resources))
        try:
            config = uvicorn.Config(app, host="0.0.0.0", port=worker_port, log_level="info")
            server = uvicorn.Server(config)
            await server.serve()
        finally:
            heartbeat_task.cancel()

    asyncio.run(_amain())
