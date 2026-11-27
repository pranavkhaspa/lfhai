"""Worker daemon - runs on each node, executes inference tasks via Ollama."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from lfhai.models import (
    ExecutionPlan,
    GPUInfo,
    Heartbeat,
    HeartbeatMetrics,
    ModelArtifact,
    NodeCapabilities,
    NodeInfo,
    NodeResources,
    RpcEndpoint,
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

llamacpp_server_bin: str = "llama-server"
llamacpp_rpc_bin: str = "ggml-rpc-server"
model_dir: str = ""
rpc_bind_host: str = "127.0.0.1"
rpc_port: int = 50052
rpc_memory_mb: int = 0
rpc_cpu_port: int = 50053
rpc_cpu_memory_mb: int = 0
rpc_gpu_port: int = 50052
rpc_gpu_memory_mb: int = 0
rpc_no_comm: bool = True
fit_target_mib: int = 0
llamacpp_threads: int = 0

rpc_lanes: list[RpcEndpoint] = []
_rpc_processes: dict[str, subprocess.Popen] = {}
_llama_servers: dict[str, tuple[subprocess.Popen, str]] = {}


def _resolve_binary(name: str) -> str | None:
    candidate = Path(name).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    if name == "ggml-rpc-server":
        return shutil.which("rpc-server")
    return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def detect_backends() -> list[str]:
    """Report which local inference engines are usable."""
    backends = []
    if ollama_client is not None:
        backends.append("ollama")
    if _resolve_binary(llamacpp_server_bin):
        backends.append("llamacpp")
    if _resolve_binary(llamacpp_rpc_bin):
        backends.append("llamacpp_rpc")
    return backends


async def discover_model_artifacts() -> list[ModelArtifact]:
    """Collect Ollama models and local GGUF files with their sizes."""
    artifacts: dict[str, ModelArtifact] = {}

    details = getattr(ollama_client, "list_model_details", None)
    if details:
        try:
            for model in await details():
                name = str(model.get("name") or model.get("model") or "")
                if name:
                    artifacts[name.lower()] = ModelArtifact(
                        name=name,
                        size_bytes=int(model.get("size") or 0),
                        backend="ollama",
                    )
        except Exception as exc:
            logger.warning("Could not inventory Ollama models: %s", exc)

    if model_dir:
        for path in sorted(Path(model_dir).expanduser().rglob("*.gguf")):
            artifacts[path.stem.lower()] = ModelArtifact(
                name=path.stem,
                size_bytes=path.stat().st_size,
                path=str(path),
                backend="llamacpp",
            )

    return list(artifacts.values())


def _rpc_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["GGML_RPC_NO_COMM"] = "1" if rpc_no_comm else "0"
    return env


_rpc_mem_supported: bool | None = None


def _rpc_server_supports_mem(binary: str) -> bool:
    global _rpc_mem_supported
    if _rpc_mem_supported is None:
        try:
            result = subprocess.run(
                [binary, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            _rpc_mem_supported = "--mem" in (result.stdout + result.stderr)
        except (OSError, subprocess.TimeoutExpired):
            _rpc_mem_supported = False
    return _rpc_mem_supported


def _start_rpc_endpoint(endpoint: RpcEndpoint) -> bool:
    binary = _resolve_binary(llamacpp_rpc_bin)
    if not binary:
        logger.warning("RPC requested but '%s' was not found in PATH", llamacpp_rpc_bin)
        return False
    host, port = endpoint.host_port
    cmd = [
        binary,
        "--host", host,
        "--port", str(port),
        "--threads", str(llamacpp_threads or os.cpu_count() or 1),
    ]
    if _rpc_server_supports_mem(binary):
        cmd.extend(["--mem", str(endpoint.memory_mb)])
    cmd.append("--cache")
    try:
        process = subprocess.Popen(
            cmd,
            env=_rpc_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        logger.warning("Could not start RPC endpoint %s: %s", endpoint.endpoint, exc)
        return False
    _rpc_processes[endpoint.endpoint] = process
    logger.info(
        "RPC endpoint listening on %s (planned %d MiB, %s)",
        endpoint.endpoint,
        endpoint.memory_mb,
        endpoint.backend,
    )
    return True


def _configured_rpc_endpoints() -> list[RpcEndpoint]:
    lanes: list[RpcEndpoint] = []
    if rpc_cpu_memory_mb > 0:
        lanes.append(
            RpcEndpoint(
                endpoint=f"{rpc_bind_host}:{rpc_cpu_port}",
                backend="cpu",
                memory_mb=rpc_cpu_memory_mb,
            )
        )
    if rpc_gpu_memory_mb > 0:
        lanes.append(
            RpcEndpoint(
                endpoint=f"{rpc_bind_host}:{rpc_gpu_port}",
                backend="cuda",
                memory_mb=rpc_gpu_memory_mb,
            )
        )
    if not lanes and rpc_memory_mb > 0:
        lanes.append(
            RpcEndpoint(
                endpoint=f"{rpc_bind_host}:{rpc_port}",
                backend="cuda" if _has_cuda() else "cpu",
                memory_mb=rpc_memory_mb,
            )
        )
    return lanes


def _has_cuda() -> bool:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _advertised_endpoints(
    endpoints: list[RpcEndpoint], advertise_ip: str | None
) -> list[RpcEndpoint]:
    if not advertise_ip:
        return endpoints
    advertised: list[RpcEndpoint] = []
    for endpoint in endpoints:
        _, port = endpoint.host_port
        advertised.append(
            endpoint.model_copy(update={"endpoint": f"{advertise_ip}:{port}"})
        )
    return advertised


def _start_rpc_server(advertise_ip: str | None = None) -> list[RpcEndpoint]:
    global rpc_lanes
    configured = _configured_rpc_endpoints()
    started: list[RpcEndpoint] = []
    for endpoint in configured:
        if _start_rpc_endpoint(endpoint):
            started.append(endpoint)
    rpc_lanes = _advertised_endpoints(started, advertise_ip)
    return rpc_lanes


def restart_rpc_processes() -> list[RpcEndpoint]:
    restarted: list[RpcEndpoint] = []
    for endpoint in _configured_rpc_endpoints():
        process = _rpc_processes.get(endpoint.endpoint)
        if process is not None and process.poll() is None:
            continue
        if process is not None:
            logger.warning("RPC endpoint %s exited; restarting", endpoint.endpoint)
        if _start_rpc_endpoint(endpoint):
            restarted.append(endpoint)
    return restarted


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
    gpu_vram_used = 0
    cuda_version = ""

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            gpu_model = parts[0].strip()
            gpu_vram = int(float(parts[1].strip())) * 1024 * 1024
            gpu_vram_used = int(float(parts[2].strip())) * 1024 * 1024
            cuda_version = parts[3].strip() if len(parts) > 3 else ""
            gpu = GPUInfo(
                model=gpu_model,
                vram_total_bytes=gpu_vram,
                vram_used_bytes=gpu_vram_used,
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
        memory_available_bytes=mem.available,
        vram_free_bytes=max(0, gpu_vram - gpu_vram_used),
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

    memory = psutil.virtual_memory()
    metrics = HeartbeatMetrics(
        cpu_usage_pct=psutil.cpu_percent(interval=0.1),
        memory_used_bytes=memory.used,
        memory_total_bytes=memory.total,
        memory_available_bytes=memory.available,
        disk_free_bytes=psutil.disk_usage("/").free,
        vram_free_bytes=resources.vram_free_bytes,
    )

    try:
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
            if resources.gpu:
                metrics.gpu_vram_free_bytes = max(
                    0, resources.gpu.vram_total_bytes - metrics.gpu_vram_used_bytes
                )
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
        restart_rpc_processes()
        await send_heartbeat(node_id, resources)
        await asyncio.sleep(heartbeat_interval)


def _model_matches(left: str, right: str) -> bool:
    def key(value: str) -> str:
        return value.strip().lower().removesuffix(".gguf").split(":", 1)[0]
    return key(left) == key(right)


def _llama_fallback_endpoints(endpoints: list[str]) -> list[list[str]]:
    attempts: list[list[str]] = []
    current = list(endpoints)
    while True:
        if current not in attempts:
            attempts.append(current)
        if not current:
            break
        current = current[:-1]
    return attempts


def _process_log_tail(handle) -> str:
    try:
        handle.seek(0)
        return handle.read()[-4096:].decode(errors="replace").strip()
    except Exception:
        return ""


async def _spawn_llama_server(
    gguf_path: str,
    endpoints: list[str],
    context_size: int,
    target_mib: int,
) -> tuple[subprocess.Popen, str]:
    binary = _resolve_binary(llamacpp_server_bin)
    if not binary:
        raise RuntimeError(f"'{llamacpp_server_bin}' not found in PATH")

    port = _free_port()
    cmd = [
        binary,
        "-m", gguf_path,
        "--host", "127.0.0.1",
        "--port", str(port),
        "-c", str(min(context_size or 4096, 32768)),
        "-ngl", "99",
    ]
    if endpoints:
        cmd.extend(["--rpc", ",".join(endpoints)])
    if target_mib > 0:
        cmd.extend(["--fit-target", str(target_mib)])
    if llamacpp_threads:
        cmd.extend(["-t", str(llamacpp_threads)])

    stderr_file = tempfile.TemporaryFile(mode="w+b")
    try:
        process = subprocess.Popen(
            cmd,
            env=_rpc_environment(),
            stdout=stderr_file,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        raise RuntimeError(f"Could not start llama-server: {exc}") from exc

    url = f"http://127.0.0.1:{port}"
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            for _ in range(300):
                if process.poll() is not None:
                    tail = _process_log_tail(stderr_file)
                    raise RuntimeError(
                        f"llama-server exited with code {process.returncode}: {tail}"
                    )
                try:
                    response = await client.get(f"{url}/health")
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError(
                    f"llama-server did not become healthy in time: {_process_log_tail(stderr_file)}"
                )
    except Exception:
        process.terminate()
        raise
    return process, url


async def _get_or_start_llama_server(plan: ExecutionPlan) -> str:
    """Start (and cache) a llama-server backed by the controller's RPC pool."""
    gguf_path = ""
    for artifact in await discover_model_artifacts():
        if artifact.path and _model_matches(artifact.name, plan.model):
            gguf_path = artifact.path
            break
    if not gguf_path:
        raise HTTPException(503, detail=f"No GGUF file found for model '{plan.model}'")

    full_endpoints = [member.rpc_endpoint for member in plan.members]
    requested_target = plan.fit_target_mib or fit_target_mib
    targets = [requested_target, 0] if requested_target > 0 else [0]
    last_error = "unknown startup failure"

    for endpoints in _llama_fallback_endpoints(full_endpoints):
        for target_mib in targets:
            cache_key = f"{gguf_path}|{','.join(endpoints)}|{plan.context_size}|{target_mib}"
            cached = _llama_servers.get(cache_key)
            if cached and cached[0].poll() is None:
                return cached[1]
            if cached:
                _llama_servers.pop(cache_key, None)
            try:
                process, url = await _spawn_llama_server(
                    gguf_path, endpoints, plan.context_size, target_mib
                )
            except RuntimeError as exc:
                last_error = str(exc)
                logger.warning(
                    "llama-server attempt failed with %d RPC peer(s), fit-target %d: %s",
                    len(endpoints),
                    target_mib,
                    exc,
                )
                continue

            _llama_servers[cache_key] = (process, url)
            logger.info(
                "llama-server ready at %s with RPC pool: %s",
                url,
                ",".join(endpoints) or "none",
            )
            return url

    raise HTTPException(500, detail=f"llama-server startup failed: {last_error}")


async def _execute_llamacpp(task: dict, plan: ExecutionPlan):
    """Execute a task against a llama-server, streaming SSE unchanged."""
    url = await _get_or_start_llama_server(plan)
    payload = {
        "model": plan.model,
        "messages": task.get("messages", []),
        "temperature": task.get("temperature", 0.7),
        "max_tokens": task.get("max_tokens", 2048),
        "stream": bool(task.get("stream")),
    }

    if not payload["stream"]:
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(f"{url}/v1/chat/completions", json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(500, detail=f"llama-server request failed: {exc}") from exc

    async def stream_result():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", f"{url}/v1/chat/completions", json=payload
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except Exception as exc:
            logger.error("llama.cpp streaming task failed: %s", exc)
            error = {"error": {"message": str(exc)}}
            yield f"data: {json.dumps(error)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_result(), media_type="text/event-stream")


# --- Worker HTTP Endpoints ---

@app.get("/worker/status")
async def worker_status() -> dict:
    artifacts = await discover_model_artifacts()
    return {
        "node_id": node_id,
        "status": "online",
        "models": [a.name for a in artifacts],
        "model_artifacts": [a.model_dump() for a in artifacts],
        "backends": detect_backends(),
        "rpc_endpoint": rpc_lanes[0].endpoint if rpc_lanes else "",
        "rpc_memory_mb": sum(endpoint.memory_mb for endpoint in rpc_lanes),
        "rpc_endpoints": [endpoint.model_dump() for endpoint in rpc_lanes],
        "fit_target_mib": fit_target_mib,
        "ollama_url": ollama_url,
    }


@app.post("/worker/task")
async def execute_task(task: dict, request: Request):
    """Execute an inference task via the backend selected by the controller."""
    if not _verify_worker_auth(request.headers.get("authorization")):
        raise HTTPException(status_code=401, detail="Not authorized")

    shard_plan = task.get("shard_plan")
    if shard_plan:
        plan = ExecutionPlan.model_validate(shard_plan)
        if plan.strategy in {"llamacpp", "rpc_pool"}:
            return await _execute_llamacpp(task, plan)

    model = task.get("model", "llama3")
    messages = task.get("messages", [])
    temperature = task.get("temperature", 0.7)
    stream = task.get("stream", False)

    if not ollama_client:
        raise HTTPException(status_code=503, detail="Ollama client not initialized")

    try:
        if stream:
            async def stream_result():
                # Translate Ollama's native chunk format into an
                # OpenAI-compatible SSE stream so every upstream proxy
                # (controller, gateway) stays transparent.
                try:
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
                                {
                                    "index": 0,
                                    "delta": {"content": delta},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(event)}\n\n"
                except Exception as e:
                    logger.error("Streaming task failed: %s", e)
                    yield f"data: {json.dumps({'error': {'message': str(e)}})}\n\n"
                finally:
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
    enable_rpc: bool = False,
    rpc_memory: int = 0,
    rpc_bind: str = "127.0.0.1",
    rpc_listen_port: int = 50052,
    models_path: str = "",
    server_binary: str = "llama-server",
    rpc_binary: str = "ggml-rpc-server",
    threads: int = 0,
    rpc_cpu: bool = False,
    rpc_cpu_memory: int = 0,
    rpc_cpu_listen_port: int = 50053,
    rpc_gpu: bool = False,
    rpc_gpu_memory: int = 0,
    rpc_gpu_listen_port: int = 50052,
    fit_target: int = 0,
    allow_rpc_comm: bool = False,
):
    global controller_url, node_id, node_secret, ollama_client, ollama_url
    global llamacpp_server_bin, llamacpp_rpc_bin, model_dir, rpc_bind_host
    global rpc_port, rpc_memory_mb, llamacpp_threads, rpc_cpu_port, rpc_cpu_memory_mb
    global rpc_gpu_port, rpc_gpu_memory_mb, rpc_no_comm, fit_target_mib
    global rpc_lanes

    import psutil

    from lfhai.credentials import load_credentials

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    controller_url = ctrl_url
    ollama_url = ollama
    ollama_client = OllamaClient(base_url=ollama)
    llamacpp_server_bin = server_binary
    llamacpp_rpc_bin = rpc_binary
    model_dir = models_path
    rpc_bind_host = rpc_bind
    rpc_port = rpc_listen_port
    llamacpp_threads = threads
    rpc_cpu_port = rpc_cpu_listen_port
    rpc_gpu_port = rpc_gpu_listen_port
    rpc_no_comm = not allow_rpc_comm
    fit_target_mib = fit_target
    rpc_cpu_memory_mb = rpc_cpu_memory
    rpc_gpu_memory_mb = rpc_gpu_memory

    if enable_rpc and not (rpc_cpu or rpc_gpu):
        rpc_cpu = True
    if rpc_cpu and not rpc_cpu_memory_mb:
        rpc_cpu_memory_mb = rpc_memory or int(
            psutil.virtual_memory().available * 0.7 / (1024**2)
        )
    if rpc_gpu and not rpc_gpu_memory_mb:
        rpc_gpu_memory_mb = int(_get_system_resources().vram_free_bytes * 0.8 / (1024**2))
    rpc_memory_mb = rpc_cpu_memory_mb or rpc_gpu_memory_mb or rpc_memory
    if not (rpc_cpu or rpc_gpu) and rpc_memory_mb and rpc_listen_port != 50052:
        rpc_port = rpc_listen_port
    rpc_lanes = []

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
        resources = _get_system_resources()
        if advertise_ip:
            resources = resources.model_copy(update={"ip": advertise_ip})
        artifacts = await discover_model_artifacts()
        endpoints = _start_rpc_server(advertise_ip)

        capabilities = NodeCapabilities(
            models=[a.name for a in artifacts],
            model_artifacts=artifacts,
            backends=detect_backends(),
            has_gpu=resources.gpu is not None,
            has_cuda=resources.gpu is not None and bool(resources.gpu.cuda_version),
            rpc_endpoint=endpoints[0].endpoint if endpoints else "",
            rpc_memory_mb=sum(endpoint.memory_mb for endpoint in endpoints),
            rpc_endpoints=endpoints,
            device_class="cuda" if endpoints and endpoints[0].backend == "cuda" else "cpu",
            fit_target_mib=fit_target_mib,
        )

        node_info = NodeInfo(
            node_id=node_id,
            hostname=resources.hostname,
            resources=resources,
            capabilities=capabilities,
            api_port=worker_port,
        )

        from lfhai.discovery import DiscoveryBeacon, DiscoveryService

        discovery = DiscoveryService(
            DiscoveryBeacon(
                node_id=node_id,
                hostname=resources.hostname,
                address=resources.ip,
                api_port=worker_port,
                rpc_endpoints=endpoints,
                model_names=[a.name for a in artifacts],
                fit_target_mib=fit_target_mib,
            )
        )
        discovery.start()

        logger.info("Worker starting on %s:%d", resources.ip, worker_port)
        logger.info("Hardware: %d cores, %d GB RAM, GPU: %s",
                    resources.cores,
                    resources.memory_total_bytes // (1024**3),
                    resources.gpu.model if resources.gpu else "none")
        logger.info("Backends: %s", capabilities.backends)
        logger.info("Models: %s", [a.name for a in artifacts])

        config = uvicorn.Config(app, host="0.0.0.0", port=worker_port, log_level="info")
        server = uvicorn.Server(config)
        serve_task = asyncio.create_task(server.serve())
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.02)
        if not server.started:
            serve_task.cancel()
            raise RuntimeError(f"Worker HTTP server failed to bind port {worker_port}")

        while True:
            ok = await register_with_controller(node_info)
            if ok:
                break
            logger.info("Retrying registration in 5s...")
            await asyncio.sleep(5)

        heartbeat_task = asyncio.create_task(heartbeat_loop(node_id, resources))
        try:
            await serve_task
        finally:
            heartbeat_task.cancel()
            discovery.stop()
            for process in _rpc_processes.values():
                if process.poll() is None:
                    process.terminate()
            for process, _ in _llama_servers.values():
                if process.poll() is None:
                    process.terminate()

    asyncio.run(_amain())
