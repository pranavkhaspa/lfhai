# Archive

Placeholder scaffolding from the original design document. These directories
were created during initial planning but have no implementation. The actual V1
code lives in the top-level `lfhai/` package.

| Directory          | Future Purpose                          | Status        |
|--------------------|-----------------------------------------|---------------|
| `agents/`          | Local operational routines              | Empty / place |
| `cli/`             | `lfh` CLI (now `lfhai/cli.py`)          | Superseded    |
| `core/controller/` | Node coordination                        | Superseded    |
| `core/inference/`  | Inference wrappers                       | Superseded    |
| `core/kv-store/`   | Raft-backed ledger (V2)                  | Planned       |
| `core/monitoring/` | Prometheus metrics                       | Planned       |
| `core/rag/`        | RAG vector indexing                      | Planned       |
| `core/registry/`   | Service discovery                        | Superseded    |
| `core/scheduler/`  | DAG scheduling (V3)                      | Planned       |
| `core/semantic-cache/` | Semantic caching                    | Planned       |
| `dashboard/`       | Web UI (V4)                              | Planned       |
| `docs/`            | Docs (now `docs-site/`)                  | Superseded    |
| `install/`         | Install scripts (now `install.sh`)       | Superseded    |
| `scripts/`         | Helper tooling                           | Empty / place |
| `worker/`          | Worker daemon (now `lfhai/worker.py`)    | Superseded    |