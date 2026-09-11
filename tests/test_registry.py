"""Tests for the node registry."""

import pytest

from lfhai.models import (
    NodeCapabilities,
    NodeInfo,
    NodeResources,
)
from lfhai.registry import NodeRegistry


@pytest.fixture
async def registry():
    reg = NodeRegistry(":memory:")
    await reg.init()
    yield reg
    await reg.close()


def make_node(node_id: str = "node-1", hostname: str = "test-host") -> NodeInfo:
    return NodeInfo(
        node_id=node_id,
        hostname=hostname,
        resources=NodeResources(
            hostname=hostname,
            ip="192.168.1.10",
            cores=8,
            memory_total_bytes=16 * 1024**3,
        ),
        capabilities=NodeCapabilities(
            models=["llama3", "whisper"],
            has_gpu=True,
        ),
    )


@pytest.mark.asyncio
async def test_register_node(registry):
    node = make_node()
    registered = await registry.register(node)
    assert registered.node_id == "node-1"
    assert registered.hostname == "test-host"


@pytest.mark.asyncio
async def test_get_node(registry):
    node = make_node()
    await registry.register(node)
    found = await registry.get_node("node-1")
    assert found is not None
    assert found.hostname == "test-host"


@pytest.mark.asyncio
async def test_list_nodes(registry):
    await registry.register(make_node("node-1", "host-a"))
    await registry.register(make_node("node-2", "host-b"))
    nodes = await registry.list_nodes()
    assert len(nodes) == 2


@pytest.mark.asyncio
async def test_heartbeat(registry):
    node = make_node()
    await registry.register(node)
    from lfhai.models import Heartbeat, HeartbeatMetrics
    hb = Heartbeat(node_id="node-1", metrics=HeartbeatMetrics(cpu_usage_pct=50.0))
    ok = await registry.heartbeat(hb)
    assert ok is True


@pytest.mark.asyncio
async def test_heartbeat_unknown_node(registry):
    from lfhai.models import Heartbeat, HeartbeatMetrics
    hb = Heartbeat(node_id="unknown", metrics=HeartbeatMetrics())
    ok = await registry.heartbeat(hb)
    assert ok is False


@pytest.mark.asyncio
async def test_remove_node(registry):
    node = make_node()
    await registry.register(node)
    ok = await registry.remove_node("node-1")
    assert ok is True
    found = await registry.get_node("node-1")
    assert found is None


@pytest.mark.asyncio
async def test_find_nodes_for_model(registry):
    await registry.register(make_node("node-1"))
    found = await registry.find_nodes_for_model("llama3")
    assert len(found) == 1
    assert found[0].node_id == "node-1"
