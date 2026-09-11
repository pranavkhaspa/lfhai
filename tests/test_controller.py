"""Tests for the controller HTTP API."""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

import lfhai.controller as controller_module
from lfhai.controller import app, init_controller, shutdown_controller


@pytest.fixture(autouse=True)
async def setup_controller():
    """Initialize controller with in-memory DB for each test."""
    await init_controller(":memory:")
    yield
    await shutdown_controller()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def join_node(client, hostname="test-host", models=("llama3",), has_gpu=True):
    """Admit a node via the join-token flow and return its credentials."""
    token_id, token_secret, _ = await controller_module.registry.create_join_token()
    node = {
        "hostname": hostname,
        "resources": {"ip": "192.168.1.10", "cores": 4},
        "capabilities": {"models": list(models), "has_gpu": has_gpu},
    }
    resp = await client.post("/api/v1/nodes/join", json={"token": token_secret, "node": node})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def register_node(client, creds, **overrides):
    node = {
        "node_id": creds["node_id"],
        "hostname": "test-host",
        "resources": {"ip": "192.168.1.10", "cores": 4},
        "capabilities": {"models": ["llama3"], "has_gpu": True},
    }
    node.update(overrides)
    return await client.post(
        "/api/v1/nodes/register",
        json=node,
        headers={"Authorization": f"Bearer {creds['node_secret']}"},
    )


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_join_then_register_and_list_nodes(client):
    creds = await join_node(client)
    assert creds["node_id"].startswith("worker-")

    resp = await register_node(client, creds)
    assert resp.status_code == 200
    assert resp.json()["node_id"] == creds["node_id"]

    resp = await client.get("/api/v1/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert any(n["node_id"] == creds["node_id"] for n in nodes)


@pytest.mark.asyncio
async def test_join_with_invalid_token(client):
    resp = await client.post(
        "/api/v1/nodes/join",
        json={"token": "not-a-real-token", "node": {"hostname": "evil-host"}},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_join_token_is_single_use(client):
    token_id, token_secret, _ = await controller_module.registry.create_join_token()
    node = {"hostname": "node-a"}
    resp = await client.post("/api/v1/nodes/join", json={"token": token_secret, "node": node})
    assert resp.status_code == 200

    resp = await client.post("/api/v1/nodes/join", json={"token": token_secret, "node": node})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_join_with_expired_token(client):
    import time

    _, token_secret, _ = await controller_module.registry.create_join_token(
        ttl_seconds=0.001
    )
    time.sleep(0.01)
    resp = await client.post(
        "/api/v1/nodes/join",
        json={"token": token_secret, "node": {"hostname": "late-host"}},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_requires_credentials(client):
    node = {
        "node_id": "worker-ghost",
        "hostname": "ghost",
        "resources": {"ip": "192.168.1.99", "cores": 1},
        "capabilities": {"models": [], "has_gpu": False},
    }
    resp = await client.post("/api/v1/nodes/register", json=node)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_with_wrong_secret(client):
    creds = await join_node(client)
    resp = await client.post(
        "/api/v1/nodes/register",
        json={"node_id": creds["node_id"], "hostname": "test-host"},
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_registration_preserves_node_secret(client):
    """Heartbeats must keep working after a worker registers (ON CONFLICT
    UPDATE, not INSERT OR REPLACE, preserves the join-issued credential)."""
    creds = await join_node(client)

    resp = await register_node(client, creds)
    assert resp.status_code == 200

    hb = {
        "node_id": creds["node_id"],
        "metrics": {"cpu_usage_pct": 10, "memory_used_bytes": 1000},
    }
    resp = await client.post(
        "/api/v1/nodes/heartbeat",
        json=hb,
        headers={"Authorization": f"Bearer {creds['node_secret']}"},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_chat_completions_route(client, monkeypatch):
    """The OpenAI-compatible chat route must dispatch to a worker and return
    a valid completion (regression: SubmitTaskRequest had no task_id)."""
    await join_node(client, hostname="gpu-node")

    async def fake_dispatch(url, payload, auth=None):
        return {"message": {"content": "hello from worker"}, "eval_count": 7}

    monkeypatch.setattr("lfhai.controller._dispatch_to_worker", fake_dispatch)

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "model": "llama3",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "hello from worker"
    assert body["id"].startswith("chatcmpl-")


@pytest.mark.asyncio
async def test_get_node(client):
    creds = await join_node(client, hostname="test-host-2")
    resp = await client.get(f"/api/v1/nodes/{creds['node_id']}")
    assert resp.status_code == 200
    assert resp.json()["hostname"] == "test-host-2"


@pytest.mark.asyncio
async def test_get_node_not_found(client):
    resp = await client.get("/api/v1/nodes/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_node(client):
    creds = await join_node(client)
    resp = await client.delete(f"/api/v1/nodes/{creds['node_id']}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/nodes/{creds['node_id']}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_heartbeat(client):
    creds = await join_node(client)
    hb = {"node_id": creds["node_id"], "metrics": {"cpu_usage_pct": 45.0}}
    resp = await client.post(
        "/api/v1/nodes/heartbeat",
        json=hb,
        headers={"Authorization": f"Bearer {creds['node_secret']}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_heartbeat_unknown_node(client):
    hb = {"node_id": "unknown-node", "metrics": {"cpu_usage_pct": 10.0}}
    resp = await client.post("/api/v1/nodes/heartbeat", json=hb)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_heartbeat_with_wrong_secret(client):
    creds = await join_node(client)
    hb = {"node_id": creds["node_id"], "metrics": {"cpu_usage_pct": 10.0}}
    resp = await client.post(
        "/api/v1/nodes/heartbeat",
        json=hb,
        headers={"Authorization": "Bearer nope"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_models(client):
    creds = await join_node(client, models=["llama3", "whisper"])
    assert creds
    resp = await client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    model_ids = [m["id"] for m in data["data"]]
    assert "llama3" in model_ids
    assert "whisper" in model_ids


@pytest.mark.asyncio
async def test_controller_dispatch_sends_bearer_auth():
    """Controller -> worker dispatch must carry the node secret as a Bearer
    credential so workers can reject unauthorized LAN clients."""
    captured: dict = {}

    def handler(request):
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = request.read()
        return httpx.Response(200, json={"message": {"content": "ok"}})

    transport = httpx.MockTransport(handler)
    await controller_module._dispatch_to_worker(
        "http://worker:8002", {"model": "llama3"}, auth="s3cret", transport=transport
    )
    assert captured["authorization"] == "Bearer s3cret"


@pytest.mark.asyncio
async def test_chat_completions_without_dispatch_secret(client):
    """If the controller has no learned secret for the chosen node, dispatch
    must be refused (503) rather than sent unauthenticated."""
    await join_node(client, hostname="gpu-node")
    node = await controller_module.router.route("llama3")
    controller_module._node_secrets.pop(node.node_id)

    resp = await client.post(
        "/v1/chat/completions",
        json={
            "model": "llama3",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
        },
    )
    assert resp.status_code == 503
