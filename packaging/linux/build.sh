#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/dist"
STAGE="$OUT/lfhai-linux-node"

python3 -m pip install --upgrade build
python3 -m build --outdir "$OUT"
mkdir -p "$STAGE"
cp "$ROOT"/dist/*.whl "$STAGE/"
cp "$ROOT/install.sh" "$STAGE/"
cp "$ROOT/packaging/linux/lfhai-worker.service" "$STAGE/"
tar -C "$OUT" -czf "$OUT/lfhai-linux-node.tar.gz" lfhai-linux-node
