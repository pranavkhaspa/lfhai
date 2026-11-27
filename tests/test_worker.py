"""Tests for the worker HTTP API (dispatch auth + task execution)."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

import lfhai.worker as worker_module
from lfhai.models import RpcEndpoint
from lfhai.worker import app


class FakeOllamaClient:
    """Minimal stand-in for OllamaClient used by the worker endpoints."""

    async def generate(self, model, messages, temperature=0.7):
        return {"message": {"role": "assistant", "content": f"fake reply to {model}"}}

    async def _stream_chat(self, payload):
        yield {"message": {"role": "assistant", "content": "chunk1"}}
        yield {"message": {"role": "assistant", "content": "chunk2"}}


@pytest.fixture(autouse=True)
def worker_config(monkeypatch):
    monkeypatch.setattr(worker_module, "node_id", "worker-test")
    monkeypatch.setattr(worker_module, "node_secret", "test-secret")
    monkeypatch.setattr(worker_module, "ollama_url", "http://localhost:11434")
    monkeypatch.setattr(worker_module, "ollama_client", FakeOllamaClient())


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


TASK = {"model": "llama3", "messages": [{"role": "user", "content": "hi"}], "stream": False}


@pytest.mark.asyncio
async def test_task_requires_auth(client):
    resp = await client.post("/worker/task", json=TASK)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_task_with_wrong_auth(client):
    resp = await client.post(
        "/worker/task", json=TASK, headers={"Authorization": "Bearer wrong"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_task_with_valid_auth(client):
    resp = await client.post(
        "/worker/task",
        json=TASK,
        headers={"Authorization": "Bearer test-secret"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"]["content"] == "fake reply to llama3"


@pytest.mark.asyncio
async def test_task_streaming(client):
    resp = await client.post(
        "/worker/task",
        json={**TASK, "stream": True},
        headers={"Authorization": "Bearer test-secret"},
    )
    assert resp.status_code == 200
    body = "".join([c.decode() async for c in resp.aiter_bytes()])
    assert "chunk1" in body
    assert "[DONE]" in body


@pytest.mark.asyncio
async def test_task_stream_error_ends_gracefully(client):
    """If Ollama dies mid-stream, the worker must emit an error event and a
    trailing [DONE] instead of hanging the proxy upstream."""

    class FailingOllama:
        async def _stream_chat(self, payload):
            yield {"message": {"role": "assistant", "content": "partial"}}
            raise RuntimeError("mock ollama died")

    worker_module.ollama_client = FailingOllama()

    resp = await client.post(
        "/worker/task",
        json={**TASK, "stream": True},
        headers={"Authorization": "Bearer test-secret"},
    )
    assert resp.status_code == 200
    body = "".join([c.decode() async for c in resp.aiter_bytes()])
    assert "partial" in body
    assert '"error"' in body
    assert '"message":' in body
    assert "[DONE]" in body


@pytest.mark.asyncio
async def test_cancel_requires_auth(client):
    resp = await client.post("/worker/cancel/abc")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cancel_with_auth(client):
    resp = await client.post(
        "/worker/cancel/abc", headers={"Authorization": "Bearer test-secret"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_supported"


def test_configured_rpc_endpoints(monkeypatch):
    monkeypatch.setattr(worker_module, "rpc_cpu_memory_mb", 1536)
    monkeypatch.setattr(worker_module, "rpc_gpu_memory_mb", 8192)
    monkeypatch.setattr(worker_module, "rpc_bind_host", "10.0.0.5")
    monkeypatch.setattr(worker_module, "rpc_cpu_port", 50053)
    monkeypatch.setattr(worker_module, "rpc_gpu_port", 50052)
    monkeypatch.setattr(worker_module, "rpc_memory_mb", 0)

    endpoints = worker_module._configured_rpc_endpoints()

    assert [(endpoint.endpoint, endpoint.backend) for endpoint in endpoints] == [
        ("10.0.0.5:50053", "cpu"),
        ("10.0.0.5:50052", "cuda"),
    ]


def test_rpc_environment_disables_peer_chatter(monkeypatch):
    monkeypatch.setattr(worker_module, "rpc_no_comm", True)

    env = worker_module._rpc_environment()

    assert env["GGML_RPC_NO_COMM"] == "1"


def test_llama_fallback_endpoints():
    attempts = worker_module._llama_fallback_endpoints(["a:1", "b:2"])

    assert attempts == [["a:1", "b:2"], ["a:1"], []]


def test_start_rpc_endpoint_command(monkeypatch):
    captured = {}

    class FakeProcess:
        def poll(self):
            return None

        def terminate(self):
            return None

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr(worker_module, "_resolve_binary", lambda _: "/usr/bin/rpc-server")
    monkeypatch.setattr(worker_module, "_rpc_server_supports_mem", lambda _: False)
    monkeypatch.setattr(worker_module, "llamacpp_threads", 4)
    monkeypatch.setattr(worker_module, "rpc_no_comm", True)
    monkeypatch.setattr(worker_module.subprocess, "Popen", fake_popen)
    worker_module._rpc_processes.clear()

    endpoint = RpcEndpoint(endpoint="10.0.0.5:50053", backend="cpu", memory_mb=1536)
    assert worker_module._start_rpc_endpoint(endpoint) is True
    assert captured["cmd"][:2] == ["/usr/bin/rpc-server", "--host"]
    assert captured["cmd"][4] == "50053"
    assert captured["cmd"][-2:] == ["4", "--cache"]
    assert captured["env"]["GGML_RPC_NO_COMM"] == "1"


def test_rpc_server_supports_mem_detection(monkeypatch):
    monkeypatch.setattr(worker_module, "_rpc_mem_supported", None)
    monkeypatch.setattr(
        worker_module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="--mem MB", stderr=""),
    )

    assert worker_module._rpc_server_supports_mem("/usr/bin/rpc-server") is True


def test_start_rpc_server_advertises_ip(monkeypatch):
    configured = [RpcEndpoint(endpoint="0.0.0.0:50053", backend="cpu", memory_mb=1536)]
    monkeypatch.setattr(worker_module, "_configured_rpc_endpoints", lambda: configured)
    monkeypatch.setattr(worker_module, "_start_rpc_endpoint", lambda _: True)

    advertised = worker_module._start_rpc_server("10.0.0.9")

    assert [endpoint.endpoint for endpoint in advertised] == ["10.0.0.9:50053"]
