"""Placement planning for single-node and pooled llama.cpp RPC execution."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lfhai.gguf import GGUFError, read_gguf_info
from lfhai.models import (
    ExecutionPlan,
    ExecutionStrategy,
    ModelArtifact,
    NodeInfo,
    NodeStatus,
    RpcEndpoint,
    ShardMember,
)

GIB = 1024**3
MIB = 1024**2
SINGLE_NODE_HEADROOM = 1.18
LEGACY_NODE_CAPACITY = 10**15


class PlanningError(RuntimeError):
    """Raised when a model cannot be placed on the current cluster."""


@dataclass(frozen=True)
class Placement:
    plan: ExecutionPlan
    message: str


def _model_key(name: str) -> str:
    return name.strip().lower().removesuffix(".gguf").split(":", 1)[0]


def _artifacts_for(model: str, nodes: list[NodeInfo]) -> list[ModelArtifact]:
    key = _model_key(model)
    found: list[ModelArtifact] = []
    for node in nodes:
        for artifact in node.capabilities.model_artifacts:
            if _model_key(artifact.name) == key:
                found.append(artifact)
    return found


def estimate_model_bytes(
    model: str, nodes: list[NodeInfo], context_size: int = 4096
) -> int:
    """Estimate resident bytes from GGUF metadata, advertised size, then name."""
    artifacts = _artifacts_for(model, nodes)
    for artifact in artifacts:
        if not artifact.path:
            continue
        try:
            info = read_gguf_info(artifact.path)
        except (GGUFError, OSError):
            continue
        return info.estimated_runtime_bytes(context_size)

    sized = [a.size_bytes for a in artifacts if a.size_bytes > 0]
    if sized:
        return max(sized) + int(max(sized) * 0.12) + context_size * 512 * 1024

    lower = model.strip().lower()
    moe = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*b\b", lower)
    if moe:
        experts = int(moe.group(1))
        params = float(moe.group(2))
        return int(experts * params * 1e9 * 0.55)

    dense = re.search(r"(\d+(?:\.\d+)?)\s*b\b", lower)
    if dense:
        return int(float(dense.group(1)) * 1e9 * 0.55)

    return 5 * GIB


def usable_bytes(node: NodeInfo) -> int:
    """RAM/VRAM this node can lend to a model, with system RAM reserved."""
    res = node.resources
    if res.memory_total_bytes == 0 and not (res.gpu and res.gpu.vram_total_bytes):
        return LEGACY_NODE_CAPACITY

    ram_free = res.memory_available_bytes or max(0, res.memory_total_bytes - res.memory_used_bytes)
    vram_total = res.gpu.vram_total_bytes if res.gpu else 0
    vram_used = res.gpu.vram_used_bytes if res.gpu else 0
    vram_free = res.vram_free_bytes or max(0, vram_total - vram_used)
    if res.memory_total_bytes == 0:
        return vram_free
    return vram_free + int(ram_free * 0.85)


def rpc_endpoints(node: NodeInfo) -> list[RpcEndpoint]:
    endpoints = node.capabilities.effective_rpc_endpoints()
    return [endpoint for endpoint in endpoints if endpoint.endpoint and endpoint.memory_mb > 0]


def rpc_capacity_bytes(node: NodeInfo) -> int:
    endpoints = rpc_endpoints(node)
    if endpoints:
        return sum(max(0, endpoint.memory_mb) * MIB for endpoint in endpoints)
    if node.capabilities.rpc_memory_mb > 0 and node.capabilities.rpc_endpoint:
        return node.capabilities.rpc_memory_mb * MIB
    return usable_bytes(node)


def fit_mib(required_bytes: int) -> int:
    return max(1, (required_bytes + MIB - 1) // MIB)


def _has_model(node: NodeInfo, model: str) -> bool:
    key = _model_key(model)
    if any(_model_key(name) == key for name in node.capabilities.models):
        return True
    return bool(_artifacts_for(model, [node]))


def _gguf_path(node: NodeInfo, model: str) -> str:
    for artifact in _artifacts_for(model, [node]):
        if artifact.path:
            return artifact.path
    return ""


def _ollama_model(node: NodeInfo, model: str) -> bool:
    key = _model_key(model)
    if any(_model_key(name) == key for name in node.capabilities.models):
        return not _gguf_path(node, model) or "ollama" in node.capabilities.backends
    return any(
        a.backend == "ollama" and _model_key(a.name) == key
        for a in node.capabilities.model_artifacts
    )


def _rank(nodes: list[NodeInfo]) -> list[NodeInfo]:
    return sorted(
        nodes,
        key=lambda n: (0 if n.capabilities.has_gpu else 1, -rpc_capacity_bytes(n)),
    )


def make_plan(
    model: str,
    nodes: list[NodeInfo],
    context_size: int = 4096,
) -> Placement:
    """Choose an execution plan that fits the requested model in free memory."""
    active = [n for n in nodes if n.status == NodeStatus.ONLINE]
    if not active:
        raise PlanningError("No online workers are available")

    model_size = estimate_model_bytes(model, active, context_size)
    required = int(model_size * SINGLE_NODE_HEADROOM)
    target_mib = fit_mib(required)
    candidates = [n for n in active if _has_model(n, model)]

    for node in _rank(candidates or active):
        capacity = rpc_capacity_bytes(node) if rpc_endpoints(node) else usable_bytes(node)
        if capacity < required:
            continue
        strategy = (
            ExecutionStrategy.OLLAMA if _ollama_model(node, model) else ExecutionStrategy.LLAMACPP
        )
        plan = ExecutionPlan(
            strategy=strategy,
            model=model,
            model_size_bytes=model_size,
            required_bytes=required,
            coordinator_node_id=node.node_id,
            context_size=context_size,
            fit_target_mib=target_mib,
        )
        return Placement(
            plan=plan,
            message=(
                f"{model} needs ~{required / GIB:.1f} GiB; using {node.hostname or node.node_id} "
                f"with {strategy.value} backend"
            ),
        )

    rpc_nodes = [n for n in active if rpc_endpoints(n)]
    if not rpc_nodes:
        raise PlanningError(
            f"{model} needs ~{required / GIB:.1f} GiB but no single worker fits and no "
            "worker advertises an RPC memory pool. Start workers with --rpc."
        )

    coordinators = [n for n in active if _gguf_path(n, model)]
    if not coordinators:
        raise PlanningError(
            f"No worker has a GGUF file for '{model}'. Use a quantized GGUF model and start "
            "the coordinator worker with --model-dir."
        )
    coordinator = _rank(coordinators)[0]

    selected: list[NodeInfo] = []
    seen: set[str] = set()
    if rpc_endpoints(coordinator):
        selected.append(coordinator)
        seen.add(coordinator.node_id)

    total = sum(rpc_capacity_bytes(n) for n in selected)
    for node in _rank(rpc_nodes):
        if node.node_id in seen:
            continue
        selected.append(node)
        seen.add(node.node_id)
        total += rpc_capacity_bytes(node)
        if total >= required:
            break

    if total < required:
        raise PlanningError(
            f"{model} needs ~{required / GIB:.1f} GiB; the RPC pool only provides "
            f"~{total / GIB:.1f} GiB across {len(selected)} worker(s)"
        )

    members: list[ShardMember] = []
    for node in selected:
        for endpoint in rpc_endpoints(node):
            members.append(
                ShardMember(
                    node_id=node.node_id,
                    rpc_endpoint=endpoint.endpoint,
                    memory_bytes=endpoint.memory_mb * MIB,
                    backend=endpoint.backend,
                    fit_target_mib=target_mib,
                )
            )

    plan = ExecutionPlan(
        strategy=ExecutionStrategy.RPC_POOL,
        model=model,
        model_size_bytes=model_size,
        required_bytes=required,
        coordinator_node_id=coordinator.node_id,
        members=members,
        context_size=context_size,
        fit_target_mib=target_mib,
    )
    return Placement(
        plan=plan,
        message=(
            f"{model} needs ~{required / GIB:.1f} GiB; streaming weights across "
            f"{len(members)} RPC device(s): " + ", ".join(m.rpc_endpoint for m in members)
        ),
    )
