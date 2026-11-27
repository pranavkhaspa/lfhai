"""Shared data models for lfhai components."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    # Joined via token but worker has not yet registered/heartbeat.
    # Not routable until the worker reports in.
    PENDING = "pending"


class GPUInfo(BaseModel):
    model: str = ""
    vram_total_bytes: int = 0
    vram_used_bytes: int = 0
    cuda_version: str = ""
    utilization_pct: float = 0.0
    temperature_celsius: float = 0.0


class NodeResources(BaseModel):
    hostname: str = ""
    ip: str = ""
    cores: int = 0
    memory_total_bytes: int = 0
    memory_used_bytes: int = 0
    memory_available_bytes: int = 0
    vram_free_bytes: int = 0
    disk_free_bytes: int = 0
    gpu: GPUInfo | None = None


class ModelArtifact(BaseModel):
    """A model file or Ollama model known to a worker."""

    name: str
    size_bytes: int = 0
    path: str = ""
    backend: str = "ollama"


class RpcEndpoint(BaseModel):
    endpoint: str
    backend: str = "cpu"
    memory_mb: int = 0
    role: str = "worker"

    @property
    def host_port(self) -> tuple[str, int]:
        host, _, port = self.endpoint.rpartition(":")
        if not host or not port.isdigit():
            raise ValueError(f"invalid RPC endpoint: {self.endpoint}")
        return host, int(port)


class NodeCapabilities(BaseModel):
    models: list[str] = Field(default_factory=list)
    model_artifacts: list[ModelArtifact] = Field(default_factory=list)
    backends: list[str] = Field(default_factory=list)
    has_gpu: bool = False
    has_cuda: bool = False
    rpc_endpoint: str = ""
    rpc_memory_mb: int = 0
    rpc_endpoints: list[RpcEndpoint] = Field(default_factory=list)
    device_class: str = "auto"
    fit_target_mib: int = 0

    def effective_rpc_endpoints(self) -> list[RpcEndpoint]:
        if self.rpc_endpoints:
            return list(self.rpc_endpoints)
        if not self.rpc_endpoint:
            return []
        return [
            RpcEndpoint(
                endpoint=self.rpc_endpoint,
                backend="cuda" if self.has_cuda else "cpu",
                memory_mb=self.rpc_memory_mb,
            )
        ]


class NodeInfo(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hostname: str = ""
    status: NodeStatus = NodeStatus.ONLINE
    resources: NodeResources = Field(default_factory=NodeResources)
    capabilities: NodeCapabilities = Field(default_factory=NodeCapabilities)
    api_port: int = 8002
    registered_at: float = Field(default_factory=time.time)
    last_heartbeat: float = Field(default_factory=time.time)


class HeartbeatMetrics(BaseModel):
    cpu_usage_pct: float = 0.0
    memory_used_bytes: int = 0
    memory_total_bytes: int = 0
    memory_available_bytes: int = 0
    gpu_usage_pct: float = 0.0
    gpu_vram_used_bytes: int = 0
    gpu_vram_free_bytes: int = 0
    gpu_temp_celsius: float = 0.0
    disk_free_bytes: int = 0


class Heartbeat(BaseModel):
    node_id: str
    timestamp: float = Field(default_factory=time.time)
    metrics: HeartbeatMetrics = Field(default_factory=HeartbeatMetrics)


class TaskStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionStrategy(str, Enum):
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    RPC_POOL = "rpc_pool"


class ShardMember(BaseModel):
    """One device contributing memory to a distributed inference plan."""

    node_id: str
    rpc_endpoint: str
    memory_bytes: int = 0
    backend: str = "cpu"
    fit_target_mib: int = 0


class ExecutionPlan(BaseModel):
    """How the controller wants a worker to execute one request."""

    strategy: ExecutionStrategy
    model: str
    model_size_bytes: int = 0
    required_bytes: int = 0
    coordinator_node_id: str
    members: list[ShardMember] = Field(default_factory=list)
    context_size: int = 4096
    fit_target_mib: int = 0
    created_at: float = Field(default_factory=time.time)


class ChatMessage(BaseModel):
    role: str
    content: str


class TaskRequest(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model: str = "llama3"
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 2048


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    node_id: str = ""
    result: Any = None
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0


class SubmitTaskRequest(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model: str = "llama3"
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 2048


class JoinRequest(BaseModel):
    """Worker asks to join the cluster with a controller-issued token."""
    token: str
    node: NodeInfo = Field(default_factory=NodeInfo)


class JoinResponse(BaseModel):
    status: str = "ok"
    node_id: str = ""
    node_secret: str = ""
