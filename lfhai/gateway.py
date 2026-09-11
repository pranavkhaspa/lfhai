"""Gateway - user-facing HTTP API that proxies to the controller."""

from __future__ import annotations

import logging

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from lfhai.models import SubmitTaskRequest

logger = logging.getLogger("lfhai.gateway")

app = FastAPI(title="lfhai Gateway", version="0.1.0")

controller_url: str = "http://localhost:8001"


@app.on_event("startup")
async def startup():
    logger.info("Gateway started, controller at %s", controller_url)


@app.post("/v1/chat/completions")
async def chat_completions(req: SubmitTaskRequest) -> dict:
    """OpenAI-compatible chat completions endpoint."""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{controller_url}/v1/chat/completions",
                json=req.model_dump(),
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Controller is unreachable")


@app.post("/v1/chat/completions/stream")
async def chat_completions_stream(req: SubmitTaskRequest):
    """Streaming chat completions endpoint."""
    req.stream = True
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{controller_url}/v1/chat/completions",
                json=req.model_dump(),
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise HTTPException(status_code=resp.status_code, detail=body.decode())

                async def proxy_stream():
                    async for chunk in resp.aiter_bytes():
                        yield chunk

                return StreamingResponse(proxy_stream(), media_type="text/event-stream")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Controller is unreachable")


@app.get("/v1/models")
async def list_models() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{controller_url}/v1/models")
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Controller is unreachable")


@app.get("/v1/nodes")
async def list_nodes() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{controller_url}/api/v1/nodes")
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Controller is unreachable")


@app.get("/health")
async def health() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{controller_url}/health")
            ctrl_ok = resp.status_code == 200
    except Exception:
        ctrl_ok = False
    return {
        "status": "ok" if ctrl_ok else "degraded",
        "controller": "connected" if ctrl_ok else "disconnected",
    }


def run_gateway(host: str = "0.0.0.0", port: int = 8000, ctrl_url: str = "http://localhost:8001"):
    global controller_url
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    controller_url = ctrl_url
    logger.info("Starting gateway on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
