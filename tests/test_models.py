"""Tests for lfhai models."""

from lfhai.models import (
    ChatMessage,
    GPUInfo,
    Heartbeat,
    HeartbeatMetrics,
    NodeCapabilities,
    NodeInfo,
    NodeStatus,
    SubmitTaskRequest,
    TaskRequest,
    TaskStatus,
)


def test_node_info_defaults():
    node = NodeInfo()
    assert node.node_id  # UUID generated
    assert node.status == NodeStatus.ONLINE
    assert node.hostname == ""


def test_heartbeat_defaults():
    hb = Heartbeat(node_id="test-123")
    assert hb.node_id == "test-123"
    assert hb.timestamp > 0
    assert isinstance(hb.metrics, HeartbeatMetrics)


def test_task_request_defaults():
    req = TaskRequest()
    assert req.task_id  # UUID generated
    assert req.model == "llama3"
    assert req.temperature == 0.7


def test_submit_task_request():
    req = SubmitTaskRequest(
        model="llama3",
        messages=[ChatMessage(role="user", content="Hello")],
    )
    assert req.model == "llama3"
    assert len(req.messages) == 1
    assert req.messages[0].content == "Hello"


def test_gpu_info():
    gpu = GPUInfo(model="RTX 3060", vram_total_bytes=12_000_000_000)
    assert gpu.model == "RTX 3060"
    assert gpu.vram_total_bytes == 12_000_000_000


def test_task_status():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.COMPLETED.value == "completed"


def test_node_capabilities():
    caps = NodeCapabilities(models=["llama3", "whisper"], has_gpu=True)
    assert "llama3" in caps.models
    assert caps.has_gpu is True
