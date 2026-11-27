#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/dist"
VERSION="${VERSION:-dev}"
LLAMA_CPP_BUILD_DIR="${LLAMA_CPP_BUILD_DIR:?set LLAMA_CPP_BUILD_DIR to the llama.cpp build directory}"
STAGE="$OUT/lfhai-linux-x86_64-$VERSION"

rm -rf "$STAGE"
mkdir -p "$STAGE/bin" "$STAGE/models" "$STAGE/scripts"
python -m PyInstaller \
    --onefile \
    --name lfh \
    --distpath "$STAGE/bin" \
    --workpath "$OUT/.pyinstaller-linux" \
    --specpath "$OUT/.pyinstaller-linux" \
    "$ROOT/packaging/cli_entry.py"

cp "$LLAMA_CPP_BUILD_DIR/bin/llama-server" "$STAGE/bin/"
cp "$LLAMA_CPP_BUILD_DIR/bin/ggml-rpc-server" "$STAGE/bin/"
cp "$LLAMA_CPP_BUILD_DIR"/bin/lib*.so* "$STAGE/bin/"
cp "$ROOT/README.md" "$STAGE/"
cp "$ROOT/LICENSE" "$STAGE/"
cp "$ROOT/install.sh" "$STAGE/"
cp "$ROOT/packaging/linux/lfhai-worker.service" "$STAGE/"
cp "$ROOT/packaging/linux/run-worker.sh" "$STAGE/"
cp "$ROOT/packaging/tailscale/setup-tailscale.sh" "$STAGE/scripts/"
cp "$ROOT/packaging/uno-q/setup-wifi.sh" "$STAGE/scripts/"
cp "$ROOT/packaging/uno-q/lfhai-wifi.env.example" "$STAGE/scripts/"

chmod +x "$STAGE/bin/lfh" "$STAGE/bin/llama-server" "$STAGE/bin/ggml-rpc-server"
chmod +x "$STAGE/install.sh" "$STAGE/run-worker.sh" "$STAGE/scripts/setup-tailscale.sh" "$STAGE/scripts/setup-wifi.sh"
tar -C "$OUT" -czf "$OUT/lfhai-linux-x86_64-$VERSION.tar.gz" "lfhai-linux-x86_64-$VERSION"
