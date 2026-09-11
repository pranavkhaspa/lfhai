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
    disk_free_bytes: int = 0
    gpu: GPUInfo | None = None


class NodeCapabilities(BaseModel):
    models: list[str] = Field(default_factory=list)
    has_gpu: bool = False
    has_cuda: bool = False


class NodeInfo(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hostname: str = ""
    status: NodeStatus = NodeStatus.ONLINE
    resources: NodeResources = Field(default_factory=NodeResources)
    capabilities: NodeCapabilities = Field(default_factory=NodeCapabilities)
    registered_at: float = Field(default_factory=time.time)
    last_heartbeat: float = Field(default_factory=time.time)


class HeartbeatMetrics(BaseModel):
    cpu_usage_pct: float = 0.0
    memory_used_bytes: int = 0
    memory_total_bytes: int = 0
    gpu_usage_pct: float = 0.0
    gpu_vram_used_bytes: int = 0
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
