"""Multi-node E2E: two real workers on different ports, routing + auth isolation.

Verifies that the controller correctly picks the right worker based on
advertised model capabilities and that per-node secrets are enforced.
"""

import asyncio
import json
import sys
import time

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

import lfhai.controller as controller_mod
from lfhai.credentials import save_credentials

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_ollama(models: list[str]) -> FastAPI:
    app = FastAPI()

    @app.get("/api/tags")
    async def tags():
        return {"models": [{"name": m, "model": m} for m in models]}

    @app.post("/api/chat")
    async def chat(body: dict):
        model = body.get("model", "llama3")
        if body.get("stream"):
            async def gen():
                chunk = {"message": {"role": "assistant", "content": f"{model}-stream"}}
                yield json.dumps(chunk) + "\n"
                yield json.dumps({"done": True}) + "\n"
            return StreamingResponse(gen(), media_type="application/x-ndjson")
        return {"message": {"role": "assistant", "content": f"{model}-reply"}, "eval_count": 5}

    return app


async def _serve(app: FastAPI):
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, f"http://127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_node_routing(tmp_path):
    servers = []
    workers = []

    try:
        # --- stub Ollama A: serves llama3 ---
        stub_a, stub_a_task, stub_a_url = await _serve(_stub_ollama(["llama3"]))
        servers.append((stub_a, stub_a_task))

        # --- stub Ollama B: serves gemma ---
        stub_b, stub_b_task, stub_b_url = await _serve(_stub_ollama(["gemma"]))
        servers.append((stub_b, stub_b_task))

        # --- controller ---
        controller_mod.controller_db_path = str(tmp_path / "ctrl.db")
        ctrl_srv, ctrl_task, ctrl_url = await _serve(controller_mod.app)
        servers.append((ctrl_srv, ctrl_task))

        # --- join worker A (llama3, CPU) ---
        _, tok_a, _ = await controller_mod.registry.create_join_token()
        async with httpx.AsyncClient(base_url=ctrl_url) as hc:
            resp = await hc.post("/api/v1/nodes/join", json={
                "token": tok_a,
                "node": {"hostname": "worker-a", "resources": {"ip": "127.0.0.1"}},
            })
            creds_a = resp.json()

        # --- join worker B (gemma, CPU) ---
        _, tok_b, _ = await controller_mod.registry.create_join_token()
        async with httpx.AsyncClient(base_url=ctrl_url) as hc:
            resp = await hc.post("/api/v1/nodes/join", json={
                "token": tok_b,
                "node": {"hostname": "worker-b", "resources": {"ip": "127.0.0.1"}},
            })
            creds_b = resp.json()

        assert creds_a["node_id"] != creds_b["node_id"]

        # --- start worker A via installed CLI in a subprocess ---
        creds_file_a = tmp_path / "creds_a.json"
        save_credentials(ctrl_url, creds_a["node_id"], creds_a["node_secret"], creds_file_a)

        proc_a = await asyncio.create_subprocess_exec(
            *[
                sys.executable, "-m", "lfhai.cli", "worker", "start",
                "-c", ctrl_url,
                "-p", "8101",
                "-o", stub_a_url,
                "-cr", str(creds_file_a),
            ],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        workers.append(proc_a)

        # --- start worker B via installed CLI ---
        creds_file_b = tmp_path / "creds_b.json"
        save_credentials(ctrl_url, creds_b["node_id"], creds_b["node_secret"], creds_file_b)

        proc_b = await asyncio.create_subprocess_exec(
            *[
                sys.executable, "-m", "lfhai.cli", "worker", "start",
                "-c", ctrl_url,
                "-p", "8102",
                "-o", stub_b_url,
                "-cr", str(creds_file_b),
            ],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        workers.append(proc_b)

        # wait for both workers to fully register (models + api_port), up to 15s
        deadline = time.time() + 20
        while time.time() < deadline:
            async with httpx.AsyncClient(base_url=ctrl_url) as hc:
                resp = await hc.get("/api/v1/nodes")
                nodes = resp.json()
            # The join-time placeholder node (ip 127.0.0.1, api_port 8002)
            # becomes useless — wait for the real registrations on 8101/8102.
            ports = {n.get("api_port") for n in nodes if n["status"] == "online"}
            if {8101, 8102} <= ports and any(n["node_id"] == creds_a["node_id"] for n in nodes):
                break
            await asyncio.sleep(0.3)
        online = [n for n in nodes if n["status"] == "online"]
        assert len(online) >= 2, f"Expected 2 online workers, got {json.dumps(online, indent=1)}"

        # --- route llama3 → worker A, gemma → worker B ---
        async with httpx.AsyncClient(base_url=ctrl_url) as hc:
            resp_a = await hc.post("/v1/chat/completions", json={
                "model": "llama3",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.7,
            })
            assert resp_a.status_code == 200, resp_a.text
            assert resp_a.json()["choices"][0]["message"]["content"] == "llama3-reply"

            resp_b = await hc.post("/v1/chat/completions", json={
                "model": "gemma",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.7,
            })
            assert resp_b.status_code == 200, resp_b.text
            assert resp_b.json()["choices"][0]["message"]["content"] == "gemma-reply"

        # --- auth isolation: dispatch to worker A with worker B's secret → 401 ---
        node_a = [n for n in online if n["node_id"] == creds_a["node_id"]][0]
        port_a = node_a["api_port"]
        async with httpx.AsyncClient() as hc:
            resp = await hc.post(
                f"http://127.0.0.1:{port_a}/worker/task",
                json={"model": "llama3", "messages": [], "stream": False},
                headers={"Authorization": f"Bearer {creds_b['node_secret']}"},
            )
            assert resp.status_code == 401

    finally:
        for srv, task in servers:
            srv.should_exit = True
            try:
                await asyncio.wait_for(task, timeout=5)
            except (asyncio.TimeoutError, Exception):
                pass
        for proc in workers:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except (asyncio.TimeoutError, Exception):
                    proc.kill()
