# CONTEXT.md — Living Project State

> This file is the **mutable memory** of the loop. Read it fully at the top of
> every iteration; update it at the end of every iteration. It records the
> current, real state of the repo and the machines so the next iteration does
> not have to re-derive it.

---

## 1. What the project is

**lfhai** = Local-First Heterogeneous AI Runtime. V1 (implemented) routes
chat-completion requests across a small cluster of nodes that each run Ollama.

- The repo implements the **V1 runtime** described in `README.md`.
- `V1_PLAN.md` and `README.md` are the design/spec references.
- The scaffold dirs under `archive/` are a preserved earlier design — ignore
  for implementation.

## 2. Architecture & ports (V1)

```
User (HTTP) --> Gateway :8000  -->  Controller :8001
                                        |  (SQLite registry + task store)
                                        v
                                     Worker :8002
                                        |
                                     Ollama :11434
```

| Component | Role | Default port |
|---|---|---|
| gateway | user-facing OpenAI-compatible API, proxies to controller | 8000 |
| controller | node registry, heartbeat, auth, routing, task store | 8001 |
| worker | per-node daemon; executes tasks via local Ollama | 8002 |
| ollama | inference backend (external, per node) | 11434 |

Modules: `lfhai/models.py` (Pydantic), `registry.py` (SQLite), `controller.py`
(FastAPI), `router.py` (node selection), `worker.py` (daemon), `ollama.py`
(client), `gateway.py`, `credentials.py`, `tailcat.py`, `cli.py` (click `lfh`).

## 3. Key data flow

join → (token minted on controller, `lfh token create`) → `lfh node join
HOST:8001:SECRET` stores `~/.lfhai/credentials.json` → `lfh worker start`
registers + heartbeats (Bearer node_secret) → controller routes chat to the
best node by model capability → worker calls local Ollama `/api/chat` →
response (JSON or SSE) streams back through controller → gateway → client.

## 4. Known findings from code review (as of this document's authoring)

These are **code-level findings** (valid on any machine). Record either "fixed"
or "still open / re-verified" as the loop progresses.

| ID | Finding | Evidence | Status |
|----|---------|----------|--------|
| F1 | Worker `-c` defaults to `localhost:8001`; install.sh hardcodes it → worker on another machine beacons to its own localhost, never registers. | `cli.py:170`, `worker.py:280`, `install.sh:178` | → H1/H8 |
| F2 | `lfh token create` and `lfh controller` both default to `lfhai.db` in the **CWD** → tokens minted in one dir are validated against another → constant 401 on join. | `cli.py:13`, `controller.py:32` | → H3 |
| F3 | Worker blocks in its register retry loop BEFORE binding uvicorn → port 8002 never opens when controller is down; worker looks dead. | `worker.py:341-354` | → H2 |
| F4 | `find_nodes_for_model` matches `gpu_model != ''` for any model, and router scores GPU first → a GPU node WITHOUT the model beats a CPU node WITH it → 500 model-not-found. | `registry.py:279-288`, `router.py:44-50` | → H4 |
| F5 | README quickstart says `lfh chat llama3`; install.sh pulls `llama3.2`. No model on node → opaque 500. Unavailable-model errors are unstructured. | `README.md:27`, `install.sh:107`, `controller.py:205-219`, `worker.py:262` | → H5/H6 |
| F6 | Gateway streaming `except httpx.ConnectError: pass` → silent empty 200. | `gateway.py:49-50` | → H6 |
| F7 | `usage` returned as `eval_count` int or `{}` (invalid OpenAI shape). | `controller.py:252-266` | → H7 |
| F8 | Worker advertises IP from `_get_local_ip()` (8.8.8.8 trick); behind NAT that IP is unreachable from the controller. `--advertise-ip` exists but is not plumbed through install.sh. | `worker.py:46-56`, `cli.py:174`, `install.sh` | → H8 |
| F9 | `lfh status` hides pending/offline nuance; no heartbeat age shown. | `cli.py:30-73` | → H9 |
| F10 | Bearer parsing/compare duplicated in controller + worker. | `controller.py:42-49`, `worker.py:37-43` | → V1-4 |
| F11 | No central config; magic values scattered everywhere. | cli/controller/gateway/worker/registry | → V1-1 |
| F12 | Docs-site wheel/version pins (e.g. `docs-site/public/lfhai-0.1.5-...whl`, `pyproject.toml` version 0.1.5) can drift from repo HEAD when new features land. Keep in sync during V1-*/V2-* work.

## 5. Environment snapshot (populate on FIRST loop run here)

The loop runs on a **different machine** than the one where this doc was
authored. Do not guess — record the real values on the first iteration:

```text
HOST (launchpad):
  OS/distro:           <from: cat /etc/os-release | head -1>
  python3 version:     <from: python3 --version>
  qemu-system-x86_64:  <present/absent>
  /dev/kvm:            <present/absent>
  ~/multipass assets:  <list: base image, seed.img, scripts>
  VM ssh user:         <from seed.img cloud-config, default "ubuntu">
  host-ports used:     2222 (controller VM ssh), 2223 (worker VM ssh),
                       8000/8001 (-> controller VM), 8002 (-> worker VM)
CONTROLLER VM:
  ssh:  ssh -p 2222 <user>@localhost
  ip:   10.0.2.15 (guest)           reachable as 10.0.2.2:<port> from other VM
WORKER VM:
  ssh:  ssh -p 2223 <user>@localhost
  ip:   10.0.2.15 (guest)           advertises --advertise-ip 10.0.2.2
CLUSTER:
  controller url seen by worker:  http://10.0.2.2:8001
  worker dispatch url (advertised): http://10.0.2.2:8002
```

## 6. REPO/Iteration state (update EVERY iteration)

```text
Last iteration:            <id + date>
Current item:              <checklist ID, e.g. H1>
Checklist progress:        <x/y Phase0, x/y Phase1>
Test suite:                <N passed, M failed>
Ruff:                      <pass/fail>
lfhai version:             <from lfhai/__init__.py>
Models on worker VM Ollama: <ollama list output>
Running processes:         <controller/gateway/worker on which VM>
Credentials present:       <on which VM; controller URL recorded>
```

## 7. WORKLOG

Chronological log of iterations. One line per iteration (or a few lines for
significant detail). Include live-test output (trimmed) for gated items.

```text
YYYY-MM-DD  <ID>  <one-line summary of change + result>
            ^ e.g. "H1: worker now beacons to credentials' controller.
            Live gate 2-4 passed: node ONLINE with no -c flag."
```

## 8. LIVE-TEST STATE (mirror of LIVE_TESTING.md)

Track which scenario steps are currently passing:

```text
END GOAL scenario (§5 in LIVE_TESTING.md) status:
  1 provision        [ ]  2 join-token mint  [ ]  3 join        [ ]
  4 node online      [ ]  5 inventory         [ ]  6 chat        [ ]
  7 chat stream      [ ]  8 wrong-model       [ ]  9 auth-401    [ ]
 10 kill/restart     [ ] 11 ctrl-restart      [ ]
```

## 9. Command cheat-sheet (run from repo root unless noted)

```bash
pip install -e ".[dev]"
ruff check lfhai/ tests/
ruff format --check lfhai/ tests/
python -m pytest tests/ -q          # :memory: + loopback only; no VMs needed
# live harness (see LIVE_TESTING.md):
ssh -p 2222 <user>@localhost        # controller VM
ssh -p 2223 <user>@localhost        # worker VM
```

## 10. "No Go" reminders (abstracted here for quick recall)

See `instructions.md §1` — scope is `/home/pro/lfhai`, `/home/pro/multipass`,
and the two VMs over SSH. No host-side installs, no ssh/ssh-dir edits, no
out-of-repo reading, no git pushes.