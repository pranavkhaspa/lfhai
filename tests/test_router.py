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


@pytest.mark.asyncio
async def test_pending_node_not_routable(setup):
    """A joined-but-unregistered node (pending) must never receive tasks —
    even if it advertises the model — until it heartbeats/registers."""
    reg, router = setup
    node = NodeInfo(
        node_id="pending-node",
        hostname="pending-host",
        resources=NodeResources(ip="10.0.0.9", cores=4),
        capabilities=NodeCapabilities(models=["llama3"], has_gpu=False),
    )
    await reg.register(node)
    await reg.set_node_status(node.node_id, "pending")
    assert await router.route("llama3") is None


@pytest.mark.asyncio
async def test_route_cpu_node_wins_on_model_match(setup):
    """A CPU-only node that explicitly advertises the requested model must
    be preferred over a GPU node that does not — proving CPU-only nodes
    can serve traffic when they have the right model."""
    reg, router = setup
    # GPU node, no models listed
    await reg.register(NodeInfo(
        node_id="gpu-no-model",
        hostname="gpu-host",
        resources=NodeResources(ip="10.0.0.2", cores=8),
        capabilities=NodeCapabilities(models=[], has_gpu=True),
    ))
    # CPU-only node that has the model
    await reg.register(NodeInfo(
        node_id="cpu-with-model",
        hostname="cpu-host",
        resources=NodeResources(ip="10.0.0.4", cores=4),
        capabilities=NodeCapabilities(models=["llama3"], has_gpu=False),
    ))

    node = await router.route("llama3")
    assert node is not None
    assert node.node_id == "cpu-with-model"


@pytest.mark.asyncio
async def test_route_cpu_only_cluster_serves_models(setup):
    """A CPU-only cluster with no GPU nodes at all must still route tasks
    to the node that advertises the requested model."""
    reg, router = setup
    await reg.register(NodeInfo(
        node_id="cpu-a",
        hostname="cpu-a",
        resources=NodeResources(ip="10.0.0.5", cores=4),
        capabilities=NodeCapabilities(models=["whisper"], has_gpu=False),
    ))
    await reg.register(NodeInfo(
        node_id="cpu-b",
        hostname="cpu-b",
        resources=NodeResources(ip="10.0.0.6", cores=8),
        capabilities=NodeCapabilities(models=["llama3", "gemma"], has_gpu=False),
    ))

    node = await router.route("llama3")
    assert node is not None
    assert node.node_id == "cpu-b"
