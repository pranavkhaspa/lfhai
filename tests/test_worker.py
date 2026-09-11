"""Tests for the worker HTTP API (dispatch auth + task execution)."""

import pytest
from httpx import ASGITransport, AsyncClient

import lfhai.worker as worker_module
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
