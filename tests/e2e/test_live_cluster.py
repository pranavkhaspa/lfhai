"""End-to-end test: real controller + real worker over HTTP + a stub Ollama.

Asserts the full production path: join -> register -> dispatch (chat) ->
streaming over real sockets. Regression guard for the integration bugs:
silent heartbeat after register, node-secret being wiped by re-register,
missing task_id on SubmitTaskRequest, and the controller->worker protocol
mismatch (/api/chat instead of /worker/task).
"""

import asyncio
import json

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

import lfhai.controller as controller_mod
import lfhai.worker as worker_mod
from lfhai.models import (
    Heartbeat,
    HeartbeatMetrics,
    NodeCapabilities,
    NodeInfo,
    NodeResources,
)
from lfhai.ollama import OllamaClient


def make_stub_ollama() -> FastAPI:
    """A tiny fake Ollama: /api/tags + /api/chat (stream + non-stream)."""
    stub = FastAPI()

    @stub.get("/api/tags")
    async def tags():
        return {"models": [{"name": "llama3", "model": "llama3"}]}

    @stub.post("/api/chat")
    async def chat(body: dict):
        if body.get("stream"):
            async def gen():
                yield json.dumps({"message": {"role": "assistant", "content": "e2e-stream"}}) + "\n"
                yield json.dumps({"done": True}) + "\n"
            return StreamingResponse(gen(), media_type="application/x-ndjson")
        return {"message": {"role": "assistant", "content": "e2e answer"}, "eval_count": 5}

    return stub


async def _serve(app: FastAPI):
    """Start a uvicorn server on a free port; returns (server, task, url)."""
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, f"http://127.0.0.1:{port}"


@pytest.mark.asyncio
async def test_full_cluster(tmp_path):
    servers = []

    try:
        # 1. Stub Ollama
        stub_srv, stub_task, stub_url = await _serve(make_stub_ollama())
        servers.append((stub_srv, stub_task))

        # 2. Controller on its own real SQLite file
        controller_mod.controller_db_path = str(tmp_path / "ctrl.db")
        ctrl_srv, ctrl_task, ctrl_url = await _serve(controller_mod.app)
        servers.append((ctrl_srv, ctrl_task))

        # 3. Join via real HTTP using a controller-issued token
        _, token_secret, _ = await controller_mod.registry.create_join_token()
        async with httpx.AsyncClient(base_url=ctrl_url) as hc:
            resp = await hc.post(
                "/api/v1/nodes/join",
                json={
                    "token": token_secret,
                    "node": {
                        "hostname": "e2e-node",
                        "resources": {"ip": "127.0.0.1"},
                    },
                },
            )
            assert resp.status_code == 200, resp.text
            creds = resp.json()

        # 4. Worker pointed at the stub Ollama, listening on a free port
        worker_mod.controller_url = ctrl_url
        worker_mod.node_id = creds["node_id"]
        worker_mod.node_secret = creds["node_secret"]
        worker_mod.ollama_url = stub_url
        worker_mod.ollama_client = OllamaClient(base_url=stub_url)
        w_srv, w_task, w_url = await _serve(worker_mod.app)
        servers.append((w_srv, w_task))
        worker_port = int(w_url.rsplit(":", 1)[1])

        node_info = NodeInfo(
            node_id=creds["node_id"],
            hostname="e2e-node",
            resources=NodeResources(ip="127.0.0.1"),
            capabilities=NodeCapabilities(models=["llama3"], has_gpu=False),
            api_port=worker_port,
        )

        # 5. Register + heartbeat via the worker's own production code path
        assert await worker_mod.register_with_controller(node_info) is True
        async with httpx.AsyncClient(base_url=ctrl_url) as hc:
            hb = Heartbeat(node_id=creds["node_id"], metrics=HeartbeatMetrics(cpu_usage_pct=5.0))
            resp = await hc.post(
                "/api/v1/nodes/heartbeat",
                json=hb.model_dump(),
                headers={"Authorization": f"Bearer {creds['node_secret']}"},
            )
            assert resp.status_code == 200, resp.text

        # 6. Gateway in front of the controller
        import lfhai.gateway as gateway_mod
        gateway_mod.controller_url = ctrl_url
        gw_srv, gw_task, gw_url = await _serve(gateway_mod.app)
        servers.append((gw_srv, gw_task))

        # 7. Non-streaming chat end-to-end through gateway -> controller -> worker -> stub
        async with httpx.AsyncClient(base_url=gw_url) as hc:
            resp = await hc.post(
                "/v1/chat/completions",
                json={
                    "model": "llama3",
                    "messages": [{"role": "user", "content": "hi"}],
                    "temperature": 0.7,
                },
            )
            assert resp.status_code == 200, resp.text
            content = resp.json()["choices"][0]["message"]["content"]
            assert content == "e2e answer"

            # 8. Streaming chat end-to-end through the gateway
            resp = await hc.post(
                "/v1/chat/completions",
                json={
                    "model": "llama3",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )
            assert resp.status_code == 200, resp.text
            body = b"".join([c async for c in resp.aiter_bytes()]).decode()
            # The worker must translate Ollama chunks into OpenAI-compatible
            # SSE: {"choices": [{"delta": {"content": ...}}]} ending in [DONE].
            chunks = [
                json.loads(line[6:])
                for line in body.splitlines()
                if line.startswith("data: ") and "[DONE]" not in line
            ]
            assert chunks, body
            deltas = [c["choices"][0]["delta"]["content"] for c in chunks]
            assert "".join(deltas) == "e2e-stream", body
            assert "[DONE]" in body
    finally:
        for srv, task in servers:
            srv.should_exit = True
            try:
                await asyncio.wait_for(task, timeout=10)
            except (asyncio.TimeoutError, Exception):
                pass
