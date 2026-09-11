# lfhai V1 Implementation Plan

## What V1 Is

A working local-first AI runtime that routes requests across heterogeneous nodes.
Two-node MVP: CPU server (controller + embeddings) + GPU workstation (LLM inference).

**NOT in V1:** DAG scheduling, Raft consensus, Tailscale mesh, Android nodes,
semantic caching, RAG, guardrails, dashboard, autonomous agents.

---

## V1 Architecture

```
User (HTTP) --> Gateway (FastAPI) --> Controller (SQLite + router)
                                          |
                                          | tailcat tunnel
                                          |
                                    Worker Node (Ollama/llama.cpp)
```

### Components

| Component   | What It Does                                   | Port  |
|-------------|------------------------------------------------|-------|
| gateway     | HTTP API for user requests, streams responses  | 8000  |
| controller  | Node registry, heartbeat tracking, task routing | 8001  |
| worker      | Runs on each node, executes inference tasks    | 8002  |

### Networking

- **V1:** Direct HTTP between components (same LAN)
- **V2:** tailcat encrypted tunnels between nodes
- **V3:** Full Tailscale mesh

---

## V1 Checklist

### Phase 1: Foundation (DO FIRST)

- [ ] Set up Python project (pyproject.toml, package layout)
- [ ] Define shared types/dataclasses (NodeInfo, Task, Heartbeat, etc.)
- [ ] Implement SQLite node registry (register, heartbeat, list, health check)
- [ ] Implement worker daemon (capability detection, Ollama proxy, task execution)
- [ ] Implement controller (routing logic, node health, task dispatch)
- [ ] Implement gateway (HTTP endpoints for chat/completions style API)
- [ ] Implement CLI (`lfh` command: status, nodes, submit, worker start)

### Phase 2: Networking & Integration

- [ ] Add tailcat support for node-to-controller communication
- [ ] Add basic logging and error handling
- [ ] Write install.sh for provisioning worker nodes

### Phase 3: Polish

- [ ] Write unit tests for controller routing, worker execution
- [ ] Integration test: submit prompt, verify response from worker
- [ ] Documentation website (after v1 works)

---

## Data Flow (V1)

```
1. User POST /v1/chat/completions {"model": "llama3", "messages": [...]}
2. Gateway receives request, forwards to Controller
3. Controller checks: which node has "llama3" capability?
   - Query SQLite: SELECT * FROM nodes WHERE capabilities LIKE '%llama3%' AND status='online'
   - Pick best node (lowest load, or first available)
4. Controller forwards task to Worker via HTTP POST /worker/task
5. Worker proxies request to local Ollama API (http://localhost:11434/api/chat)
6. Worker streams response back to Controller
7. Controller streams response back to Gateway
8. Gateway streams response back to User
```

---

## API Contracts (V1)

### Gateway Endpoints
```
POST /v1/chat/completions    - OpenAI-compatible chat endpoint
POST /v1/embeddings          - Text embedding endpoint (future)
GET  /v1/models              - List available models across cluster
GET  /health                 - Gateway health check
```

### Controller Endpoints
```
POST /api/v1/nodes/register  - Node registration
POST /api/v1/nodes/heartbeat - Node heartbeat with metrics
GET  /api/v1/nodes           - List all nodes
GET  /api/v1/nodes/{id}      - Get node details
POST /api/v1/tasks/submit    - Submit task for routing
GET  /api/v1/tasks/{id}      - Get task status
```

### Worker Endpoints
```
GET  /worker/status          - Worker status + capabilities
POST /worker/task            - Execute inference task
POST /worker/cancel/{id}     - Cancel running task
```

---

## File Structure (V1)

```
lfhai/
├── lfhai/
│   ├── __init__.py
│   ├── models.py           # Shared types
│   ├── gateway.py          # HTTP API gateway
│   ├── controller.py       # Node registry + router
│   ├── worker.py           # Worker daemon
│   ├── router.py           # Task routing logic
│   ├── ollama.py           # Ollama API client
│   └── cli.py              # lfh CLI tool
├── pyproject.toml
├── install.sh
└── V1_PLAN.md
```

---

## Tech Stack (V1)

- **Language:** Python 3.10+
- **HTTP Framework:** FastAPI + uvicorn
- **Database:** SQLite (via aiosqlite for async)
- **Inference Backend:** Ollama (HTTP API at localhost:11434)
- **Networking V1:** Direct HTTP on LAN
- **Networking V2:** tailcat (Tailscale's encrypted tunnel)
- **CLI:** Click
- **Testing:** pytest + httpx

---

## What Makes V1 Different From Just Using Ollama Directly

1. **Multi-node routing** - prompt goes to whichever node has the right model
2. **Capability-aware scheduling** - knows which node has GPU, which has CPU
3. **Heartbeat monitoring** - detects dead nodes, stops routing to them
4. **Unified API** - one endpoint for all models across all nodes
5. **Extensible** - V2 adds tailcat tunnels, V3 adds DAG scheduling

---

## Key Decisions

1. **SQLite over Raft** - V1 is single-controller, no consensus needed
2. **FastAPI over raw sockets** - faster to build, good streaming support
3. **Ollama as backend** - don't reinvent model serving, Ollama already does it well
4. **No Tailscale in V1** - direct HTTP on LAN, add tailcat in V2
5. **Python over Go** - faster iteration for MVP, can rewrite hot paths later
