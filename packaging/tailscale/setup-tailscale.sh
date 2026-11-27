#!/usr/bin/env bash
set -euo pipefail

if ! command -v tailscale >/dev/null 2>&1; then
    curl -fsSL https://tailscale.com/install.sh | sh
fi

EXTRA_ARGS="${TAILSCALE_EXTRA_ARGS:-}"
if [[ -n "${TAILSCALE_AUTHKEY:-}" ]]; then
    tailscale up --authkey="$TAILSCALE_AUTHKEY" --ssh $EXTRA_ARGS
else
    tailscale up --ssh $EXTRA_ARGS
fi

tailscale status
tailscale ip -4
