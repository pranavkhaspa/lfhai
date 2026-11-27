#!/usr/bin/env bash
set -euo pipefail

JOIN_TOKEN="${1:?usage: setup.sh HOST:PORT:SECRET [ADVERTISE_IP]}"
ADVERTISE_IP="${2:-${LFHAI_ADVERTISE_IP:-}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -n "${LFHAI_WIFI_ENV:-}" ]]; then
    bash "$SCRIPT_DIR/setup-wifi.sh" "$LFHAI_WIFI_ENV"
    if [[ -z "$ADVERTISE_IP" ]]; then
        source "$LFHAI_WIFI_ENV"
        ADVERTISE_IP="${LFHAI_ADVERTISE_IP:-}"
    fi
fi

ARGS=(
    --join-token "$JOIN_TOKEN"
    --rpc-cpu
    --rpc-cpu-memory-mb 1536
    --rpc-cpu-port 50053
    --rpc-bind 0.0.0.0
    --llamacpp-bin llama-server
    --rpc-bin ggml-rpc-server
)
if [[ -n "$ADVERTISE_IP" ]]; then
    ARGS+=(--advertise-ip "$ADVERTISE_IP")
fi

bash "$ROOT/install.sh" "${ARGS[@]}"
