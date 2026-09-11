#!/usr/bin/env bash
# lfhai V1 install script
# Provisions a node with lfhai worker + Ollama
#
# Usage:
#   curl -sSL <url>/install.sh | bash
#   or: bash install.sh [--controller-url http://controller:8001] [--port 8002]
#
set -euo pipefail

CONTROLLER_URL="http://localhost:8001"
WORKER_PORT=8002
OLLAMA_URL="http://localhost:11434"
JOIN_TOKEN="${LFHAI_JOIN_TOKEN:-}"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --controller-url) CONTROLLER_URL="$2"; shift 2 ;;
        --port) WORKER_PORT="$2"; shift 2 ;;
        --ollama-url) OLLAMA_URL="$2"; shift 2 ;;
        --join-token) JOIN_TOKEN="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo "============================================"
echo "  lfhai V1 Worker Install"
echo "============================================"
echo ""
echo "Controller: $CONTROLLER_URL"
echo "Worker Port: $WORKER_PORT"
echo "Ollama URL: $OLLAMA_URL"
echo "Join Token: $([[ -n "$JOIN_TOKEN" ]] && echo "provided" || echo "none (requires lfh node join)")"
echo ""

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux)  PLATFORM="linux" ;;
    Darwin) PLATFORM="macos" ;;
    *)      echo "Unsupported OS: $OS"; exit 1 ;;
esac

echo "[1/5] Checking prerequisites..."

# Check Python 3.10+
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 10 ]]; then
        echo "  Python $PY_VERSION ✓"
    else
        echo "  Python 3.10+ required (found $PY_VERSION)"
        exit 1
    fi
else
    echo "  Python3 not found. Installing..."
    if [[ "$PLATFORM" == "linux" ]]; then
        sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
    elif [[ "$PLATFORM" == "macos" ]]; then
        brew install python@3.12
    fi
fi

# Check/install Ollama
echo ""
echo "[2/5] Checking Ollama..."
if command -v ollama &>/dev/null; then
    echo "  Ollama installed ✓"
else
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Ensure Ollama is running
if ! curl -s "$OLLAMA_URL/api/tags" &>/dev/null; then
    echo "  Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
fi

# Pull a default model if no models exist
MODEL_COUNT=$(curl -s "$OLLAMA_URL/api/tags" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(len(data.get('models', [])))
" 2>/dev/null || echo "0")

if [[ "$MODEL_COUNT" -eq "0" ]]; then
    echo "  No models found. Pulling llama3.2 (small)..."
    ollama pull llama3.2
fi

# Install Python dependencies
echo ""
echo "[3/5] Installing lfhai..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    echo "  Installing from source..."
    cd "$SCRIPT_DIR"
else
    echo "  Installing from PyPI..."
    SCRIPT_DIR=$(mktemp -d)
    cd "$SCRIPT_DIR"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install lfhai
fi

if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -e . 2>/dev/null || pip install lfhai

echo "  lfhai installed ✓"

# Join the cluster (required once per machine)
echo ""
echo "[4/6] Joining cluster..."
if [[ -n "$JOIN_TOKEN" ]]; then
    if lfh node join "$JOIN_TOKEN" &>/dev/null; then
        echo "  Joined cluster ✓"
    else
        echo "  Join failed. Retrying in 5s..."
        until lfh node join "$JOIN_TOKEN" &>/dev/null; do sleep 5; done
        echo "  Joined cluster ✓"
    fi
else
    echo "  No --join-token provided."
    echo "  Generate one on the controller: lfh token create"
    echo "  Then join this machine with:     lfh node join <token>"
fi

# Create systemd service (optional, Linux only)
echo ""
echo "[5/6] Setting up worker service..."
if [[ "$PLATFORM" == "linux" ]] && command -v systemctl &>/dev/null; then
    SERVICE_FILE="/etc/systemd/system/lfhai-worker.service"
    VENV_PATH="$(pwd)/.venv"
    LFHAI_PATH="$(pwd)"

    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=lfhai Worker Daemon
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$LFHAI_PATH
ExecStart=$VENV_PATH/bin/python -m lfhai.cli worker start -c $CONTROLLER_URL -p $WORKER_PORT -o $OLLAMA_URL
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable lfhai-worker
    echo "  Systemd service created ✓"
    echo "  To start: sudo systemctl start lfhai-worker"
else
    echo "  Systemd not available. Start manually:"
    echo "    lfh worker start -c $CONTROLLER_URL -p $WORKER_PORT -o $OLLAMA_URL"
fi

# Show what models are available
echo ""
echo "[6/6] Available models:"
curl -s "$OLLAMA_URL/api/tags" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    print(f'  - {m[\"name\"]}')
" 2>/dev/null || echo "  (none)"

echo ""
echo "============================================"
echo "  Install complete!"
echo "============================================"
echo ""
echo "Start the worker:"
echo "  lfh worker start -c $CONTROLLER_URL -p $WORKER_PORT"
echo "Or if systemd was set up:"
echo "  sudo systemctl start lfhai-worker"
echo ""
echo "Test with:"
echo "  lfh status"
echo "  lfh chat llama3.2 'Hello!'"
