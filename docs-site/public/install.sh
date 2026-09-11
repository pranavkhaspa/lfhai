#!/usr/bin/env bash
# lfhai install script
# Provisions a node with lfhai worker + Ollama and optionally joins the cluster.
#
# Usage (single machine, single command):
#   From the controller, first run:  lfh token create
#   Then on each worker machine:
#     curl -fsSL <site-url>/install.sh | bash -s -- --join-token <TOKEN>
#
# Or manually:
#   bash install.sh [--controller-url http://host:8001] [--port 8002]
#                   [--ollama-url http://localhost:11434]
#                   [--join-token HOST:PORT:SECRET]
#                   [--pip-url https://.../lfhai.whl]
#
set -euo pipefail

CONTROLLER_URL="http://localhost:8001"
WORKER_PORT=8002
OLLAMA_URL="http://localhost:11434"
JOIN_TOKEN="${LFHAI_JOIN_TOKEN:-}"
LFHAI_ROOT="${LFHAI_ROOT:-$HOME/.lfhai}"
LFHAI_BIN="$LFHAI_ROOT/venv/bin"
LFHAI_WHEEL_URL="${LFHAI_WHEEL_URL:-https://lfhai.vercel.app/lfhai-0.1.0-py3-none-any.whl}"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --controller-url) CONTROLLER_URL="$2"; shift 2 ;;
        --port) WORKER_PORT="$2"; shift 2 ;;
        --ollama-url) OLLAMA_URL="$2"; shift 2 ;;
        --join-token) JOIN_TOKEN="$2"; shift 2 ;;
        --pip-url) LFHAI_WHEEL_URL="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo "============================================"
echo "  lfhai Worker Install"
echo "============================================"
echo ""
echo "Controller: $CONTROLLER_URL"
echo "Worker Port: $WORKER_PORT"
echo "Ollama URL: $OLLAMA_URL"
JOIN_STATUS="none (requires lfh node join)"
[[ -n "$JOIN_TOKEN" ]] && JOIN_STATUS="provided"
echo "Join Token: $JOIN_STATUS"
echo "Install Dir: $LFHAI_ROOT"
echo ""

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Linux)  PLATFORM="linux" ;;
    Darwin) PLATFORM="macos" ;;
    *)      echo "Unsupported OS: $OS"; exit 1 ;;
esac

echo "[1/6] Checking prerequisites..."

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
echo "[2/6] Checking Ollama..."
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

# Install lfhai
echo ""
echo "[3/6] Installing lfhai..."
SRC="${BASH_SOURCE[0]:-}"
mkdir -p "$LFHAI_ROOT"

if [[ -n "$SRC" && -f "$(dirname "$SRC")/pyproject.toml" ]]; then
    # Running from a repository checkout: install the local source.
    LOCAL_DIR="$(cd "$(dirname "$SRC")" && pwd)"
    echo "  Installing from source ($LOCAL_DIR)..."
    python3 -m venv "$LFHAI_ROOT/venv"
    "$LFHAI_BIN/pip" install -e "$LOCAL_DIR"
else
    # Served from the website: install the packaged wheel (works even if
    # the GitHub repo is private, no credentials needed).
    echo "  Installing from wheel ($LFHAI_WHEEL_URL)..."
    python3 -m venv "$LFHAI_ROOT/venv"
    "$LFHAI_BIN/pip" install "$LFHAI_WHEEL_URL"
fi

echo "  lfhai installed ✓ ($LFHAI_BIN/lfh)"

# Put lfh on PATH permanently so it works in any new shell
echo "  Linking lfh into \$PATH..."
mkdir -p "$HOME/.local/bin"
ln -sf "$LFHAI_BIN/lfh" "$HOME/.local/bin/lfh"
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.zshrc" 2>/dev/null \
        || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc" 2>/dev/null \
        || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "  lfh on PATH ✓ (new shells automatically; this one too)"
export PATH="$LFHAI_BIN:$PATH"

# Join the cluster (required once per machine, before the worker can register)
JOINED=0
if [[ -n "$JOIN_TOKEN" ]]; then
    echo ""
    echo "[4/6] Joining cluster..."
    if "$LFHAI_BIN/lfh" node join "$JOIN_TOKEN" &>/dev/null; then
        echo "  Joined cluster ✓"
        JOINED=1
    else
        echo "  Join failed. Retrying in 5s..."
        until "$LFHAI_BIN/lfh" node join "$JOIN_TOKEN" &>/dev/null; do sleep 5; done
        echo "  Joined cluster ✓"
        JOINED=1
    fi
fi

# Create systemd service (Linux) or run the daemon in the background
echo ""
echo "[5/6] Setting up worker service..."
if [[ "$PLATFORM" == "linux" ]] && command -v systemctl &>/dev/null; then
    SERVICE_FILE="/etc/systemd/system/lfhai-worker.service"

    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=lfhai Worker Daemon
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$LFHAI_ROOT
ExecStart=$LFHAI_BIN/lfh worker start -c $CONTROLLER_URL -p $WORKER_PORT -o $OLLAMA_URL
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable lfhai-worker &>/dev/null
    echo "  Systemd service created ✓"
    if [[ "$JOINED" -eq 1 ]] || [[ -f "$HOME/.lfhai/credentials.json" ]]; then
        sudo systemctl start lfhai-worker
        echo "  Worker started ✓"
    else
        echo "  Run: lfh node join <token>   then: sudo systemctl start lfhai-worker"
    fi
else
    if [[ "$JOINED" -eq 1 ]]; then
        nohup "$LFHAI_BIN/lfh" worker start -c "$CONTROLLER_URL" -p "$WORKER_PORT" -o "$OLLAMA_URL" &>/dev/null &
        echo "  Worker started in background ✓"
    else
        echo "  Run: lfh node join <token>   then: lfh worker start"
    fi
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
if [[ "$JOINED" -eq 1 ]]; then
    echo "To add another machine, mint a fresh token and reuse this command:"
    echo "  lfh token create"
    echo "  curl -fsSL <site-url>/install.sh | bash -s -- --join-token <TOKEN>"
fi
echo ""
echo "Check the cluster from any machine (controller side):"
echo "  lfh status"
echo "  lfh chat llama3.2 'Hello!'"
echo ""