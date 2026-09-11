"""Controller - the central coordinator for lfhai cluster."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from lfhai.models import (
    Heartbeat,
    JoinRequest,
    JoinResponse,
    NodeInfo,
    SubmitTaskRequest,
)
from lfhai.registry import NodeRegistry, TaskStore
from lfhai.router import TaskRouter

logger = logging.getLogger("lfhai.controller")

# Global state
registry: NodeRegistry | None = None
task_store: TaskStore | None = None
router: TaskRouter | None = None
controller_db_path: str = "lfhai.db"
JOIN_GUIDANCE = "Run: lfh node join <token> (get a token with: lfh token create)"

# Plaintext per-node secrets kept in MEMORY ONLY (never written to disk).
# Recovered from the Authorization header on each register/heartbeat, so a
# controller restart needs no persisted plaintext. Used to authenticate
# controller -> worker task dispatch.
_node_secrets: dict[str, str] = {}


def _bearer_secret(authorization: str | None) -> str | None:
    """Extract the raw secret from an Authorization: Bearer header."""
    if not authorization:
        return None
    scheme, _, rest = authorization.partition(" ")
    if scheme.lower() != "bearer" or not rest:
        return None
    return rest.strip()


async def heartbeat_checker():
    """Background task that marks stale nodes offline."""
    while True:
        if registry:
            stale = await registry.mark_offline_stale_nodes()
            if stale:
                logger.warning("Nodes went offline: %s", stale)
        await asyncio.sleep(5)


async def init_controller(db_path: str = "lfhai.db"):
    """Initialize the controller's global state."""
    global registry, task_store, router
    registry = NodeRegistry(db_path)
    await registry.init()
    router = TaskRouter(registry)
    task_store = TaskStore(registry._db)
    asyncio.create_task(heartbeat_checker())
    logger.info("Controller initialized")


async def shutdown_controller():
    """Clean up the controller's global state."""
    global registry
    if registry:
        await registry.close()
        registry = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_controller(controller_db_path)
    yield
    await shutdown_controller()


app = FastAPI(title="lfhai Controller", version="0.1.0", lifespan=lifespan)


# --- Node Management ---

@app.post("/api/v1/nodes/join")
async def join_cluster(req: JoinRequest) -> JoinResponse:
    """Admit a new node using a controller-issued join token.

    Validates the one-time token, assigns a server-side node ID, and hands
    back a per-node secret used to authenticate register/heartbeat calls.
    """
    token_id = await registry.consume_join_token(req.token)
    if not token_id:
        raise HTTPException(
            status_code=401, detail=f"Invalid, expired, or used join token. {JOIN_GUIDANCE}"
        )

    node_id = f"worker-{req.node.hostname or 'node'}-{secrets.token_urlsafe(4)}"
    node = req.node.model_copy(update={"node_id": node_id})
    registered = await registry.register(node)

    node_secret = secrets.token_urlsafe(24)
    await registry.set_node_secret(registered.node_id, node_secret)
    await registry.mark_join_token_used(token_id, registered.node_id, registered.hostname)
    _node_secrets[registered.node_id] = node_secret

    logger.info("Node joined cluster: %s (%s)", registered.hostname, registered.node_id)
    return JoinResponse(node_id=registered.node_id, node_secret=node_secret)


@app.post("/api/v1/nodes/register")
async def register_node(
    node: NodeInfo, authorization: str | None = Header(default=None)
) -> dict:
    secret = _bearer_secret(authorization)
    if not await registry.verify_node(node.node_id, secret or ""):
        raise HTTPException(status_code=401, detail=f"Not authorized. {JOIN_GUIDANCE}")
    if secret:
        _node_secrets[node.node_id] = secret
    registered = await registry.register(node)
    logger.info("Node registered: %s (%s)", registered.hostname, registered.node_id)
    return {"status": "ok", "node_id": registered.node_id}


@app.post("/api/v1/nodes/heartbeat")
async def node_heartbeat(
    hb: Heartbeat, authorization: str | None = Header(default=None)
) -> dict:
    existing = await registry.get_node(hb.node_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Node not registered")
    secret = _bearer_secret(authorization)
    if not await registry.verify_node(hb.node_id, secret or ""):
        raise HTTPException(status_code=401, detail=f"Not authorized. {JOIN_GUIDANCE}")
    if secret:
        _node_secrets[hb.node_id] = secret
    ok = await registry.heartbeat(hb)
    if not ok:
        raise HTTPException(status_code=404, detail="Node not registered")
    return {"status": "ok"}


@app.get("/api/v1/nodes")
async def list_nodes() -> list[dict]:
    nodes = await registry.list_nodes(include_offline=True)
    return [n.model_dump() for n in nodes]


@app.get("/api/v1/nodes/{node_id}")
async def get_node(node_id: str) -> dict:
    node = await registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node.model_dump()


@app.delete("/api/v1/nodes/{node_id}")
async def remove_node(node_id: str) -> dict:
    ok = await registry.remove_node(node_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "removed"}


# --- Task Management ---

async def _dispatch_to_worker(
    worker_url: str,
    payload: dict,
    auth: str | None = None,
    transport=None,
) -> dict:
    """Send a (non-streaming) inference task to a worker and return the parsed JSON.

    Streaming requests are proxied separately in chat_completions. Both use
    the node secret as an Authorization: Bearer credential so only the
    controller can dispatch work to a node.
    """
    import httpx as _httpx

    headers = {"Authorization": f"Bearer {auth}"} if auth else None
    async with _httpx.AsyncClient(timeout=None, transport=transport) as hc:
        resp = await hc.post(f"{worker_url}/worker/task", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


@app.post("/v1/chat/completions")
async def chat_completions(req: SubmitTaskRequest) -> dict:
    """OpenAI-compatible chat completions endpoint."""
    import httpx as _httpx

    node = await router.route(req.model)
    if not node:
        raise HTTPException(
            status_code=503,
            detail=f"No nodes available for model '{req.model}'. "
                   f"Register a worker with this model first.",
        )

    messages = [m.model_dump() for m in req.messages]
    node_secret = _node_secrets.get(node.node_id)
    if not node_secret:
        raise HTTPException(
            status_code=503,
            detail=f"No dispatch credential for node '{node.node_id}'. "
                   "Node must complete register before dispatch.",
        )

    await task_store.create_task(req.task_id, req.model, messages)
    await task_store.update_task(req.task_id, status="dispatched", assigned_node=node.node_id)

    worker_port = node.api_port or 8002
    worker_url = f"http://{node.resources.ip}:{worker_port}"
    payload = {
        "model": req.model,
        "messages": messages,
        "temperature": req.temperature,
        "stream": req.stream,
        "task_id": req.task_id,
    }

    try:
        await task_store.update_task(req.task_id, status="running", started_at=time.time())

        if req.stream:
            async def proxy_sse():
                headers = {"Authorization": f"Bearer {node_secret}"}
                async with _httpx.AsyncClient(timeout=None) as pc:
                    endpoint = f"{worker_url}/worker/task"
                    async with pc.stream("POST", endpoint, json=payload, headers=headers) as stream:
                        async for chunk in stream.aiter_bytes():
                            yield chunk

            return StreamingResponse(proxy_sse(), media_type="text/event-stream")

        result = await _dispatch_to_worker(worker_url, payload, auth=node_secret)
        await task_store.update_task(
            req.task_id, status="completed", result=str(result), completed_at=time.time()
        )
        return {
            "id": f"chatcmpl-{req.task_id[:8]}",
            "object": "chat.completion",
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result.get("message", {}).get("content", ""),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": result.get("eval_count", {}),
        }
    except Exception as e:
        await task_store.update_task(
            req.task_id, status="failed", error=str(e), completed_at=time.time()
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models() -> dict:
    """List all available models across the cluster."""
    nodes = await registry.list_nodes()
    models = set()
    for node in nodes:
        models.update(node.capabilities.models)
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "owned_by": "lfhai"} for m in sorted(models)],
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "component": "controller"}


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    task = await task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def run_controller(host: str = "0.0.0.0", port: int = 8001, db_path: str = "lfhai.db"):
    global controller_db_path
    controller_db_path = db_path
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    logger.info("Starting controller on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
