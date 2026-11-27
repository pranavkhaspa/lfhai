"""Minimal GGUF header reader for capacity planning."""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

GGUF_MAGIC = b"GGUF"

_TYPE_UINT8 = 0
_TYPE_INT8 = 1
_TYPE_UINT16 = 2
_TYPE_INT16 = 3
_TYPE_UINT32 = 4
_TYPE_INT32 = 5
_TYPE_FLOAT32 = 6
_TYPE_BOOL = 7
_TYPE_STRING = 8
_TYPE_ARRAY = 9
_TYPE_UINT64 = 10
_TYPE_INT64 = 11
_TYPE_FLOAT64 = 12

_TENSOR_LAYOUTS: dict[int, tuple[int, int]] = {
    0: (1, 4),
    1: (1, 2),
    2: (32, 18),
    3: (32, 20),
    4: (32, 26),
    5: (32, 28),
    6: (32, 34),
    7: (32, 40),
    8: (256, 84),
    9: (256, 110),
    10: (256, 144),
    11: (256, 176),
    12: (256, 210),
    13: (256, 292),
    14: (256, 65),
    15: (256, 73),
    16: (256, 79),
    17: (256, 96),
    18: (256, 87),
    19: (256, 95),
    20: (256, 83),
    21: (256, 104),
    22: (1, 1),
    23: (1, 2),
    24: (1, 4),
    25: (1, 8),
    26: (1, 8),
    27: (256, 32),
    28: (32, 20),
    29: (256, 73),
    30: (1, 2),
}

_SCALAR_FORMATS = {
    _TYPE_UINT8: "<B",
    _TYPE_INT8: "<b",
    _TYPE_UINT16: "<H",
    _TYPE_INT16: "<h",
    _TYPE_UINT32: "<I",
    _TYPE_INT32: "<i",
    _TYPE_FLOAT32: "<f",
    _TYPE_BOOL: "<?",
    _TYPE_UINT64: "<Q",
    _TYPE_INT64: "<q",
    _TYPE_FLOAT64: "<d",
}


class GGUFError(ValueError):
    pass


@dataclass(frozen=True)
class GGUFInfo:
    path: str
    size_bytes: int
    version: int
    tensor_count: int
    architecture: str
    quant_type: str
    parameter_count: int
    tensor_bytes: int
    metadata: dict[str, Any]

    def estimated_runtime_bytes(self, context_size: int = 4096) -> int:
        arch = self.architecture
        layers = int(self.metadata.get(f"{arch}.block_count", 0) or 0)
        embd = int(self.metadata.get(f"{arch}.embedding_length", 0) or 0)
        heads = int(self.metadata.get(f"{arch}.attention.head_count", 0) or 0)
        kv_heads = int(self.metadata.get(f"{arch}.attention.head_count_kv", heads) or heads)
        if layers and embd and heads and kv_heads and context_size:
            head_dim = embd // heads
            kv_bytes = 2 * context_size * layers * head_dim * kv_heads * 2
        else:
            kv_bytes = int(self.size_bytes * 0.03)
        overhead = max(64 * 1024**2, int(self.size_bytes * 0.06))
        return self.size_bytes + kv_bytes + overhead


def _read_exact(handle: BinaryIO, size: int) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise GGUFError("unexpected end of GGUF file")
    return data


def _read_scalar(handle: BinaryIO, value_type: int) -> Any:
    fmt = _SCALAR_FORMATS.get(value_type)
    if not fmt:
        raise GGUFError(f"unsupported scalar type {value_type}")
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, _read_exact(handle, size))[0]


def _read_string(handle: BinaryIO) -> str:
    length = struct.unpack("<Q", _read_exact(handle, 8))[0]
    return _read_exact(handle, length).decode("utf-8", errors="replace")


def _read_value(handle: BinaryIO, value_type: int) -> Any:
    if value_type == _TYPE_STRING:
        return _read_string(handle)
    if value_type == _TYPE_ARRAY:
        item_type = struct.unpack("<I", _read_exact(handle, 4))[0]
        count = struct.unpack("<Q", _read_exact(handle, 8))[0]
        if item_type == _TYPE_STRING:
            return [_read_string(handle) for _ in range(count)]
        return [_read_scalar(handle, item_type) for _ in range(count)]
    return _read_scalar(handle, value_type)


def _quant_type(path: Path, metadata: dict[str, Any]) -> str:
    name = str(metadata.get("general.name") or path.name)
    pattern = r"\b(IQ\d+_[A-Z]+|Q\d+_K_[A-Z]+|Q\d+_[01]|Q[2-8]_K|BF16|F16|F32)\b"
    match = re.search(pattern, name.upper())
    if match:
        return match.group(1)
    return "unknown"


def _tensor_bytes(dims: list[int], tensor_type: int) -> int:
    layout = _TENSOR_LAYOUTS.get(tensor_type)
    if layout is None or not dims:
        return 0
    elements = math.prod(dims)
    block_size, block_bytes = layout
    return math.ceil(elements / block_size) * block_bytes


def read_gguf_info(path: str | Path) -> GGUFInfo:
    source = Path(path).expanduser()
    with source.open("rb") as handle:
        header = _read_exact(handle, 24)
        magic, version, tensor_count, kv_count = struct.unpack("<4sIQQ", header)
        if magic != GGUF_MAGIC:
            raise GGUFError(f"not a GGUF file: {source}")
        metadata: dict[str, Any] = {}
        for _ in range(kv_count):
            key = _read_string(handle)
            value_type = struct.unpack("<I", _read_exact(handle, 4))[0]
            metadata[key] = _read_value(handle, value_type)

        tensor_bytes = 0
        parameter_count = 0
        for _ in range(tensor_count):
            _read_string(handle)
            dim_count = struct.unpack("<I", _read_exact(handle, 4))[0]
            dims = [struct.unpack("<Q", _read_exact(handle, 8))[0] for _ in range(dim_count)]
            tensor_type = struct.unpack("<I", _read_exact(handle, 4))[0]
            _read_exact(handle, 8)
            size = _tensor_bytes(dims, tensor_type)
            tensor_bytes += size
            parameter_count += math.prod(dims)

    architecture = str(metadata.get("general.architecture", "") or "")
    return GGUFInfo(
        path=str(source),
        size_bytes=source.stat().st_size,
        version=version,
        tensor_count=tensor_count,
        architecture=architecture,
        quant_type=_quant_type(source, metadata),
        parameter_count=parameter_count,
        tensor_bytes=tensor_bytes,
        metadata=metadata,
    )
