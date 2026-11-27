#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LD_LIBRARY_PATH="$DIR/bin:${LD_LIBRARY_PATH:-}"

ARGS=(
    worker start
    --llamacpp-bin "$DIR/bin/llama-server"
    --rpc-bin "$DIR/bin/ggml-rpc-server"
    --model-dir "${LFHAI_MODEL_DIR:-$DIR/models}"
)
if [[ -n "${LFHAI_RPC_BIND:-}" ]]; then
    ARGS+=(--rpc-bind "$LFHAI_RPC_BIND")
fi
if [[ -n "${LFHAI_RPC_CPU_MEMORY_MB:-}" ]]; then
    ARGS+=(--rpc-cpu --rpc-cpu-memory-mb "$LFHAI_RPC_CPU_MEMORY_MB")
fi
if [[ -n "${LFHAI_RPC_GPU_MEMORY_MB:-}" ]]; then
    ARGS+=(--rpc-gpu --rpc-gpu-memory-mb "$LFHAI_RPC_GPU_MEMORY_MB")
fi
if [[ -n "${LFHAI_FIT_TARGET_MIB:-}" ]]; then
    ARGS+=(--fit-target-mib "$LFHAI_FIT_TARGET_MIB")
fi

exec "$DIR/bin/lfh" -c "${LFHAI_CONTROLLER:-http://127.0.0.1:8001}" "${ARGS[@]}" "$@"
