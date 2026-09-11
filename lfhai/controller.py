"""Controller - the central coordinator for lfhai cluster."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from lfhai.models import (
    Heartbeat,
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
    await init_controller()
    yield
    await shutdown_controller()


app = FastAPI(title="lfhai Controller", version="0.1.0", lifespan=lifespan)


# --- Node Management ---

@app.post("/api/v1/nodes/register")
async def register_node(node: NodeInfo) -> dict:
    registered = await registry.register(node)
    logger.info("Node registered: %s (%s)", registered.hostname, registered.node_id)
    return {"status": "ok", "node_id": registered.node_id}


@app.post("/api/v1/nodes/heartbeat")
async def node_heartbeat(hb: Heartbeat) -> dict:
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

@app.post("/v1/chat/completions")
async def chat_completions(req: SubmitTaskRequest) -> dict:
    """OpenAI-compatible chat completions endpoint."""
    from lfhai.ollama import OllamaClient

    node = await router.route(req.model)
    if not node:
        raise HTTPException(
            status_code=503,
            detail=f"No nodes available for model '{req.model}'. "
                   f"Register a worker with this model first.",
        )

    messages = [m.model_dump() for m in req.messages]
    await task_store.create_task(req.task_id, req.model, messages)
    await task_store.update_task(req.task_id, status="dispatched", assigned_node=node.node_id)

    worker_url = f"http://{node.resources.ip}:8002"
    client = OllamaClient(base_url=worker_url)

    try:
        await task_store.update_task(req.task_id, status="running", started_at=time.time())

        if req.stream:
            async def stream_response():
                try:
                    async for chunk in client._stream_chat({
                        "model": req.model,
                        "messages": messages,
                        "stream": True,
                        "options": {"temperature": req.temperature},
                    }):
                        import json
                        yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                    await task_store.update_task(
                        req.task_id, status="completed", completed_at=time.time()
                    )
                except Exception as e:
                    await task_store.update_task(
                        req.task_id, status="failed", error=str(e), completed_at=time.time()
                    )
                    yield f'data: {{"error": "{str(e)}"}}\n\n'

            return StreamingResponse(stream_response(), media_type="text/event-stream")
        else:
            result = await client.generate(
                model=req.model,
                messages=messages,
                temperature=req.temperature,
            )
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
    finally:
        await client.close()


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


def run_controller(host: str = "0.0.0.0", port: int = 8001):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    logger.info("Starting controller on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
