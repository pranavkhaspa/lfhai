"""Tests for 70B placement and RPC memory pooling."""

import pytest

from lfhai.models import (
    ExecutionStrategy,
    ModelArtifact,
    NodeCapabilities,
    NodeInfo,
    NodeResources,
    RpcEndpoint,
)
from lfhai.planner import PlanningError, make_plan, usable_bytes

GIB = 1024**3


def node(
    name: str,
    *,
    free_gib: float,
    endpoint: str = "",
    artifact: ModelArtifact | None = None,
    models: list[str] | None = None,
    backends: list[str] | None = None,
    endpoints: list[RpcEndpoint] | None = None,
) -> NodeInfo:
    return NodeInfo(
        node_id=name,
        hostname=name,
        resources=NodeResources(
            ip=f"10.0.0.{len(name) + 1}",
            memory_total_bytes=int((free_gib + 1) * GIB),
            memory_available_bytes=int(free_gib * GIB),
        ),
        capabilities=NodeCapabilities(
            models=models or ([artifact.name] if artifact else []),
            model_artifacts=[artifact] if artifact else [],
            backends=backends or [],
            rpc_endpoint=endpoint,
            rpc_memory_mb=int(free_gib * 1024) if endpoint else 0,
            rpc_endpoints=endpoints or [],
        ),
    )


def test_single_node_fits_70b():
    artifact = ModelArtifact(name="llama3:70b", size_bytes=40 * GIB, backend="ollama")
    nodes = [
        node("big", free_gib=80, artifact=artifact, backends=["ollama"]),
    ]

    placement = make_plan("llama3:70b", nodes)

    assert placement.plan.strategy == ExecutionStrategy.OLLAMA
    assert placement.plan.required_bytes > 40 * GIB
    assert placement.plan.coordinator_node_id == "big"
    assert placement.plan.members == []


def test_70b_estimate_from_name():
    nodes = [node("big", free_gib=60, models=["llama3:70b"], backends=["ollama"])]

    placement = make_plan("llama3:70b", nodes)

    assert placement.plan.model_size_bytes == int(70 * 1e9 * 0.55)
    assert placement.plan.strategy == ExecutionStrategy.OLLAMA


def test_pools_rpc_devices_when_no_single_node_fits():
    artifact = ModelArtifact(
        name="llama-3.3-70b-instruct.Q4_K_M",
        size_bytes=40 * GIB,
        path="/models/llama-3.3-70b.Q4_K_M.gguf",
        backend="llamacpp",
    )
    coordinator = node(
        "coordinator",
        free_gib=20,
        endpoint="10.0.0.1:50052",
        artifact=artifact,
        backends=["llamacpp", "llamacpp_rpc"],
    )
    helpers = [
        node("helper-a", free_gib=24, endpoint="10.0.0.2:50052", backends=["llamacpp_rpc"]),
        node("helper-b", free_gib=24, endpoint="10.0.0.3:50052", backends=["llamacpp_rpc"]),
    ]

    placement = make_plan("llama-3.3-70b-instruct.Q4_K_M.gguf", [coordinator, *helpers])

    assert placement.plan.strategy == ExecutionStrategy.RPC_POOL
    assert placement.plan.coordinator_node_id == "coordinator"
    assert [m.rpc_endpoint for m in placement.plan.members] == [
        "10.0.0.1:50052",
        "10.0.0.2:50052",
        "10.0.0.3:50052",
    ]
    assert sum(m.memory_bytes for m in placement.plan.members) >= placement.plan.required_bytes


def test_uses_explicit_multi_backend_endpoints_and_fit_target():
    artifact = ModelArtifact(
        name="llama-3.3-70b-instruct.Q4_K_M",
        size_bytes=40 * GIB,
        path="/models/llama-3.3-70b.Q4_K_M.gguf",
        backend="llamacpp",
    )
    coordinator = node(
        "coordinator",
        free_gib=20,
        artifact=artifact,
        backends=["llamacpp", "llamacpp_rpc"],
        endpoints=[
            RpcEndpoint(
                endpoint="10.0.0.1:50052", backend="cuda", memory_mb=20 * 1024
            )
        ],
    )
    helpers = [
        node(
            "phone",
            free_gib=2,
            backends=["llamacpp_rpc"],
            endpoints=[
                RpcEndpoint(
                    endpoint="10.0.0.2:50053", backend="cpu", memory_mb=1536
                )
            ],
        ),
        node(
            "uno-q",
            free_gib=2,
            backends=["llamacpp_rpc"],
            endpoints=[
                RpcEndpoint(
                    endpoint="10.0.0.3:50053", backend="cpu", memory_mb=1536
                )
            ],
        ),
        node(
            "laptop",
            free_gib=33,
            backends=["llamacpp_rpc"],
            endpoints=[
                RpcEndpoint(
                    endpoint="10.0.0.4:50053", backend="cpu", memory_mb=33 * 1024
                )
            ],
        ),
    ]

    placement = make_plan("llama-3.3-70b-instruct.Q4_K_M", [coordinator, *helpers])

    assert placement.plan.strategy == ExecutionStrategy.RPC_POOL
    assert placement.plan.fit_target_mib > 0
    assert [member.backend for member in placement.plan.members] == [
        "cuda",
        "cpu",
        "cpu",
        "cpu",
    ]
    assert all(
        member.fit_target_mib == placement.plan.fit_target_mib
        for member in placement.plan.members
    )


def test_rejects_pool_that_is_too_small():
    artifact = ModelArtifact(
        name="qwen2.5-72b",
        size_bytes=43 * GIB,
        path="/models/qwen2.5-72b.gguf",
        backend="llamacpp",
    )
    nodes = [
        node("coordinator", free_gib=12, endpoint="10.0.0.1:50052", artifact=artifact),
        node("helper", free_gib=12, endpoint="10.0.0.2:50052"),
    ]

    with pytest.raises(PlanningError, match="RPC pool only provides"):
        make_plan("qwen2.5-72b", nodes)


def test_requires_rpc_endpoints_for_oversized_model():
    artifact = ModelArtifact(name="llama3:70b", size_bytes=40 * GIB, backend="ollama")
    nodes = [node("small", free_gib=16, artifact=artifact, backends=["ollama"])]

    with pytest.raises(PlanningError, match="no worker advertises an RPC memory pool"):
        make_plan("llama3:70b", nodes)


def test_usable_bytes_reserves_system_ram():
    target = node("reserve", free_gib=20)
    assert usable_bytes(target) == int(20 * GIB * 0.85)
