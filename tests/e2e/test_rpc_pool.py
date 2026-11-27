"""E2E: a 70B request pools two workers through an RPC plan and streams SSE."""

import asyncio
import json

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

import lfhai.controller as controller_mod
import lfhai.worker as worker_mod
from lfhai.models import ModelArtifact, NodeCapabilities, NodeInfo, NodeResources

MODEL = "llama3:70b"
GIB = 1024**3


def make_stub_llama_server() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/v1/chat/completions")
    async def completions(body: dict):
        if body.get("stream"):

            async def chunks():
                for token in ("pooled ", "answer"):
                    event = {
                        "id": "chunk-1",
                        "object": "chat.completion.chunk",
                        "model": MODEL,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(event)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(chunks(), media_type="text/event-stream")

        return {
            "id": "chatcmpl-pooled",
            "choices": [{"message": {"role": "assistant", "content": "pooled answer"}}],
            "usage": {"completion_tokens": 2},
        }

    return app


async def serve(app: FastAPI):
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, f"http://127.0.0.1:{port}"


async def join(client, hostname: str) -> dict:
    _, secret, _ = await controller_mod.registry.create_join_token()
    resp = await client.post(
        "/api/v1/nodes/join",
        json={
            "token": secret,
            "node": {"hostname": hostname, "resources": {"ip": "127.0.0.1"}},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_rpc_pool_plan_and_streaming(tmp_path, monkeypatch):
    servers = []

    stub_srv, stub_task, stub_url = await serve(make_stub_llama_server())
    servers.append((stub_srv, stub_task))

    controller_mod.controller_db_path = str(tmp_path / "ctrl.db")
    ctrl_srv, ctrl_task, ctrl_url = await serve(controller_mod.app)
    servers.append((ctrl_srv, ctrl_task))

    worker_srv, worker_task, worker_url = await serve(worker_mod.app)
    servers.append((worker_srv, worker_task))
    worker_port = int(worker_url.rsplit(":", 1)[1])

    monkeypatch.setattr(worker_mod, "controller_url", ctrl_url)
    monkeypatch.setattr(worker_mod, "ollama_client", None)
    monkeypatch.setattr(worker_mod, "model_dir", "/models")
    monkeypatch.setattr(worker_mod, "_get_or_start_llama_server", lambda plan: _ready(stub_url))

    artifact = ModelArtifact(
        name=MODEL,
        size_bytes=40 * GIB,
        path="/models/llama3-70b-Q4_K_M.gguf",
        backend="llamacpp",
    )
    coordinator = NodeInfo(
        hostname="coordinator",
        resources=NodeResources(
            ip="127.0.0.1", memory_total_bytes=21 * GIB, memory_available_bytes=20 * GIB
        ),
        capabilities=NodeCapabilities(
            models=[MODEL],
            model_artifacts=[artifact],
            backends=["llamacpp", "llamacpp_rpc"],
            rpc_endpoint="10.0.0.1:50052",
            rpc_memory_mb=20 * 1024,
        ),
        api_port=worker_port,
    )

    async with httpx.AsyncClient(base_url=ctrl_url) as client:
        creds = await join(client, "coordinator")
        coordinator.node_id = creds["node_id"]
        monkeypatch.setattr(worker_mod, "node_id", creds["node_id"])
        monkeypatch.setattr(worker_mod, "node_secret", creds["node_secret"])

        resp = await client.post(
            "/api/v1/nodes/register",
            json=coordinator.model_dump(),
            headers={"Authorization": f"Bearer {creds['node_secret']}"},
        )
        assert resp.status_code == 200, resp.text

        helper_creds = await join(client, "helper")
        helper = NodeInfo(
            node_id=helper_creds["node_id"],
            hostname="helper",
            resources=NodeResources(
                ip="10.0.0.2", memory_total_bytes=41 * GIB, memory_available_bytes=40 * GIB
            ),
            capabilities=NodeCapabilities(
                backends=["llamacpp_rpc"],
                rpc_endpoint="10.0.0.2:50052",
                rpc_memory_mb=40 * 1024,
            ),
        )
        resp = await client.post(
            "/api/v1/nodes/register",
            json=helper.model_dump(),
            headers={"Authorization": f"Bearer {helper_creds['node_secret']}"},
        )
        assert resp.status_code == 200, resp.text

        for node_id, secret in (
            (creds["node_id"], creds["node_secret"]),
            (helper_creds["node_id"], helper_creds["node_secret"]),
        ):
            resp = await client.post(
                "/api/v1/nodes/heartbeat",
                json={"node_id": node_id},
                headers={"Authorization": f"Bearer {secret}"},
            )
            assert resp.status_code == 200, resp.text

        plan_resp = await client.post("/api/v1/plan", json={"model": MODEL})
        assert plan_resp.status_code == 200, plan_resp.text
        plan = plan_resp.json()["plan"]
        assert plan["strategy"] == "rpc_pool"
        assert {m["rpc_endpoint"] for m in plan["members"]} == {"10.0.0.1:50052", "10.0.0.2:50052"}

        body = {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}
        resp = await client.post("/v1/chat/completions", json=body)
        assert resp.status_code == 200, resp.text
        assert resp.json()["choices"][0]["message"]["content"] == "pooled answer"

        resp = await client.post("/v1/chat/completions", json={**body, "stream": True})
        assert resp.status_code == 200, resp.text
        sse = b"".join([chunk async for chunk in resp.aiter_bytes()]).decode()
        deltas = [
            json.loads(line[6:])["choices"][0]["delta"]["content"]
            for line in sse.splitlines()
            if line.startswith("data: ") and "[DONE]" not in line
        ]
        assert "".join(deltas) == "pooled answer"
        assert "[DONE]" in sse

    try:
        for srv, task in servers:
            srv.should_exit = True
            await asyncio.wait_for(task, timeout=10)
    except (asyncio.TimeoutError, Exception):
        pass


async def _ready(url: str) -> str:
    return url
