"""Tests for the task router."""

import pytest

from lfhai.models import NodeCapabilities, NodeInfo, NodeResources
from lfhai.registry import NodeRegistry
from lfhai.router import TaskRouter


@pytest.fixture
async def setup():
    reg = NodeRegistry(":memory:")
    await reg.init()
    router = TaskRouter(reg)
    yield reg, router
    await reg.close()


@pytest.mark.asyncio
async def test_route_to_gpu_node(setup):
    reg, router = setup
    # CPU-only node
    await reg.register(NodeInfo(
        node_id="cpu-node",
        hostname="cpu-host",
        resources=NodeResources(ip="10.0.0.1", cores=4),
        capabilities=NodeCapabilities(models=[], has_gpu=False),
    ))
    # GPU node
    await reg.register(NodeInfo(
        node_id="gpu-node",
        hostname="gpu-host",
        resources=NodeResources(
            ip="10.0.0.2", cores=8,
        ),
        capabilities=NodeCapabilities(models=["llama3"], has_gpu=True),
    ))

    node = await router.route("llama3")
    assert node is not None
    assert node.node_id == "gpu-node"


@pytest.mark.asyncio
async def test_route_no_nodes(setup):
    _, router = setup
    node = await router.route("llama3")
    assert node is None


@pytest.mark.asyncio
async def test_route_fallback_to_any_online(setup):
    reg, router = setup
    await reg.register(NodeInfo(
        node_id="any-node",
        hostname="any-host",
        resources=NodeResources(ip="10.0.0.3"),
        capabilities=NodeCapabilities(models=[], has_gpu=False),
    ))
    node = await router.route("some-model")
    assert node is not None
    assert node.node_id == "any-node"
