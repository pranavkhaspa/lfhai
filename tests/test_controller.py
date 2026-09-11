"""Tests for the controller HTTP API."""

import pytest
from httpx import ASGITransport, AsyncClient

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


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_and_list_nodes(client):
    node = {
        "node_id": "test-node-1",
        "hostname": "test-host",
        "resources": {"ip": "192.168.1.10", "cores": 4},
        "capabilities": {"models": ["llama3"], "has_gpu": True},
    }
    resp = await client.post("/api/v1/nodes/register", json=node)
    assert resp.status_code == 200
    assert resp.json()["node_id"] == "test-node-1"

    resp = await client.get("/api/v1/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert len(nodes) >= 1


@pytest.mark.asyncio
async def test_get_node(client):
    node = {
        "node_id": "test-node-2",
        "hostname": "test-host-2",
        "resources": {"ip": "192.168.1.11", "cores": 8},
        "capabilities": {"models": ["whisper"], "has_gpu": False},
    }
    await client.post("/api/v1/nodes/register", json=node)
    resp = await client.get("/api/v1/nodes/test-node-2")
    assert resp.status_code == 200
    assert resp.json()["hostname"] == "test-host-2"


@pytest.mark.asyncio
async def test_get_node_not_found(client):
    resp = await client.get("/api/v1/nodes/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_node(client):
    node = {
        "node_id": "test-node-3",
        "hostname": "test-host-3",
        "resources": {"ip": "192.168.1.12", "cores": 2},
        "capabilities": {"models": [], "has_gpu": False},
    }
    await client.post("/api/v1/nodes/register", json=node)
    resp = await client.delete("/api/v1/nodes/test-node-3")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/nodes/test-node-3")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_heartbeat(client):
    node = {
        "node_id": "test-hb-node",
        "hostname": "hb-host",
        "resources": {"ip": "10.0.0.5", "cores": 2},
        "capabilities": {"models": [], "has_gpu": False},
    }
    await client.post("/api/v1/nodes/register", json=node)

    hb = {
        "node_id": "test-hb-node",
        "metrics": {"cpu_usage_pct": 45.0},
    }
    resp = await client.post("/api/v1/nodes/heartbeat", json=hb)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_heartbeat_unknown_node(client):
    hb = {"node_id": "unknown-node", "metrics": {"cpu_usage_pct": 10.0}}
    resp = await client.post("/api/v1/nodes/heartbeat", json=hb)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_models(client):
    # Register a node with models
    node = {
        "node_id": "model-node",
        "hostname": "model-host",
        "resources": {"ip": "10.0.0.6", "cores": 4},
        "capabilities": {"models": ["llama3", "whisper"], "has_gpu": True},
    }
    await client.post("/api/v1/nodes/register", json=node)
    resp = await client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    model_ids = [m["id"] for m in data["data"]]
    assert "llama3" in model_ids
    assert "whisper" in model_ids
