import struct

import pytest

from lfhai.gguf import GGUFError, read_gguf_info


def _string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def _key_value(key: str, value_type: int, value: bytes) -> bytes:
    return _string(key) + struct.pack("<I", value_type) + value


def _sample_gguf() -> bytes:
    metadata = b"".join(
        [
            _key_value("general.architecture", 8, _string("llama")),
            _key_value("general.name", 8, _string("tiny-Q4_K_M.gguf")),
            _key_value("llama.block_count", 4, struct.pack("<I", 2)),
            _key_value("llama.embedding_length", 4, struct.pack("<I", 16)),
            _key_value("llama.attention.head_count", 4, struct.pack("<I", 2)),
            _key_value("llama.attention.head_count_kv", 4, struct.pack("<I", 1)),
        ]
    )
    tensor = _string("blk.0.attn_q.weight")
    tensor += struct.pack("<I", 1)
    tensor += struct.pack("<Q", 16)
    tensor += struct.pack("<I", 10)
    tensor += struct.pack("<Q", 0)
    return struct.pack("<4sIQQ", b"GGUF", 3, 1, 6) + metadata + tensor


def test_read_gguf_info(tmp_path):
    path = tmp_path / "tiny-Q4_K_M.gguf"
    path.write_bytes(_sample_gguf())

    info = read_gguf_info(path)

    assert info.version == 3
    assert info.architecture == "llama"
    assert info.quant_type == "Q4_K_M"
    assert info.tensor_count == 1
    assert info.tensor_bytes == 144
    assert info.estimated_runtime_bytes(4096) > path.stat().st_size


def test_rejects_non_gguf(tmp_path):
    path = tmp_path / "bad.gguf"
    path.write_bytes(b"not a gguf")

    with pytest.raises(GGUFError):
        read_gguf_info(path)
