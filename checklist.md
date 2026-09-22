# CHECKLIST.md — Features Backlog (Single Source of Truth)

> Consumed by the loop. Only edit via the workflow in `instructions.md`.
> An item becomes `[x]` **exclusively** when it passes the full Definition of
> Done in `instructions.md §4` — implementation, tests, lint, AI review, code
> review, **live 2-VM test**, docs update.
>
> Order matters: complete items in the order listed within each phase. Earlier
> items unblock later ones. See `instructions.md §5` for status markers.
>
> Phases required for the END GOAL: **Phase 0 + Phase 1**. Phase 2 stays as
> future roadmap.

---

## Item template (what each field means)

- **What** — the single behavior being added/fixed.
- **Why** — the bug/evidence this addresses (file:line references from code
  review).
- **How** — approach, modules touched, SOLID / Separation-of-Concerns / DRY
  mapping.
- **Acceptance** — bulleted, independently testable criteria.
- **Tests** — the specific unit/integration/e2e/regression cases to add.
- **Live gate** — the numbered step(s) in `LIVE_TESTING.md §5` scenario that
  this item must pass (or `No live gate`).

---

# PHASE 0 — HARDENING (REQUIRED FOR END GOAL)

## H1 — Worker derives its controller URL from saved credentials
- **Status:** `[ ]`
- **What:** When a worker starts without an explicit `--controller-url/-c`,
  it must use the `controller` value stored in `~/.lfhai/credentials.json`
  (written by `lfh node join`). `localhost:8001` is only the last-resort
  default when no credentials exist.
- **Why:** `cli.py:170` and `worker.py:280` default to `localhost:8001`, and
  `install.sh:178` hardcodes `-c http://localhost:8001` in the systemd unit.
  On a separate worker machine that points at the machine's OWN localhost, so
  the worker never reaches the controller → node never comes online → the
  cluster is dead. The join token already carries the controller address, and
  `credentials.json` already stores it — the worker just ignores it.
- **How:**
  - `lfhai/worker.py:run_worker` — resolve `ctrl_url` from creds when the caller
    passed the default/None. CLI currently passes a default string; change the
    CLI to pass `None` when unset (`cli.py:170`) so "unset" is distinguishable.
  - `lfhai/credentials.py` — already exposes `load_credentials`; reuse it (DRY).
  - SoC: worker owns credential loading via `credentials.py`; CLI stops baking
    a wrong default.
- **Acceptance:**
  - `lfh worker start` (no `-c`) after a successful `lfh node join` registers
    with the controller stored in credentials, not localhost.
  - `lfh worker start -c http://other:8001` still overrides credentials.
  - With no credentials file, behavior unchanged (defaults to localhost, logs
    the join hint).
  - No behavior change for tests that pass `-c` explicitly.
- **Tests:**
  - Unit: build fake credentials in a tmp dir; monkeypatch
    `lfhai.worker.load_credentials` (or point `run_worker` at the tmp file) and
    assert the resolved controller URL equals the credentials' controller.
  - Unit: explicit `-c` wins over credentials.
  - Unit: no credentials → localhost default.
  - CLI: `lfh worker start` wiring passes `None` when `-c` omitted
    (monkeypatch `run_worker`, assert arg).
  - Regression: assert that with creds present and no `-c`, the URL is NOT
    localhost.
- **Live gate:** Steps 2–4 (join on worker VM → node ONLINE in controller with
  NO `-c` flag on `lfh worker start`).

## H2 — Worker serves HTTP before registration completes
- **Status:** `[ ]`
- **What:** `run_worker` currently blocks in the register-retry loop
  (`worker.py:341-354`) and only starts uvicorn AFTER registration succeeds.
  If the controller is down, the worker's own port 8002 never opens, so
  `lfh worker status` and `/health` report nothing — the worker looks dead
  even though it is running.
- **Why:** Observed in live testing: a worker pointed at a dead controller
  retried registration forever and never bound port 8002.
- **How:** Start uvicorn first; run registration + heartbeats as background
  tasks with retry/backoff. Keep SoC: a `_register_loop` coroutine owning the
  retry, a separate `_heartbeat_loop`, and the HTTP server starting immediately.
- **Acceptance:**
  - `GET /worker/status` and `GET /health` answer (200) even when the
    controller is unreachable.
  - Worker converges to ONLINE once the controller becomes reachable (no
    restart needed).
  - Heartbeats only start after a successful registration (no heartbeat spam
    before identity is accepted), but `/health` reports `ollama` status
    regardless.
- **Tests:**
  - Integration: start worker app with unreachable controller URL;
    `GET /worker/status` returns 200; then reachable controller → registers.
  - Unit: retry loop stops after successful register.
- **Live gate:** Steps 2–5 (worker starts, then controller comes up, node goes
  ONLINE without restarting the worker).

## H3 — Stable controller DB path shared by CLI and controller
- **Status:** `[ ]`
- **What:** `lfh token create` and `lfh controller` (and `lfh token list/
  revoke`) must default to the SAME database regardless of the working
  directory they are launched from. Default: `~/.lfhai/controller.db`.
- **Why:** `cli.py:13-14` and `controller.py:32` both default to `lfhai.db`
  in the CWD. If the user mints a token from one directory and the controller
  runs from another, the token is stored in a different DB than the one the
  controller validates → every join gets
  `401 Invalid, expired, or used join token` (controller.py:100-104).
- **How:**
  - Add `controller_db_path()` in `lfhai/config.py` (created in `V1-1`, but
    this item may introduce the function in `lfhai/credentials.py` or a small
    `lfhai/paths.py` module with SoC in mind — prefer a single place).
  - Controller lifespan and all CLI token commands use it when `--db` is not
    explicitly given.
  - Keep `--db` explicit override working.
- **Acceptance:**
  - `lfh token create` then `lfh controller` from a *different* directory
    accepts the token (join succeeds).
  - `lfh token list` from a different directory sees the same tokens.
  - Explicit `--db /custom/path.db` still isolates as before.
- **Tests:**
  - Integration: set HOME to tmp; run `lfh token create` (via CliRunner) in dir
    A and assert the controller app initialized with the same path accepts the
    minted token.
  - Unit: `controller_db_path()` returns `~/.lfhai/controller.db`.
  - Regression: joining with a token minted in a different CWD works.
- **Live gate:** Steps 2–3 (token minted on controller VM, join consumed on
  worker VM — naturally different filesystems, so this exercises the stable
  path on the controller machine).
- **Note:** after this lands, `--db lfhai.db` calls in existing tests must be
  re-checked (many pass an explicit db path — fine).

## H4 — Strict model-aware routing
- **Status:** `[ ]`
- **What:** Routing must dispatch a model to nodes that actually advertise it.
  Remove the `gpu_model != ''` hijack and stop "any online node" fallback for
  models nobody has.
- **Why:** `registry.py:279-288` matches `(capabilities LIKE '%model%' OR
  gpu_model != '')` — a GPU node with ANY GPU matches EVERY model. And
  `router.py:44-50` scores GPU first. Result: a GPU node that does NOT have the
  requested model is preferred over a CPU node that DOES → Ollama 404 →
  opaque 500. CPU-only nodes (a stated V1 goal) get starved.
- **How:**
  - `registry.py:find_nodes_for_model` — match on capabilities only; add a
    `has_model` query that does exact-ish matching. Keep model name comparison
    tolerant of Ollama `:tag` suffixes (`llama3.2` matches `llama3.2:latest`).
  - `router.py:route` — decide: exact capability match wins; NO silent
    fallback to arbitrary nodes. If nobody has the model, return None and let
    the controller produce H5's structured error.
- **Acceptance:**
  - Request for model M goes only to nodes whose capabilities include M
    (tolerating `:tag`).
  - GPU node without M is never chosen when a CPU node has M.
  - No node has M → no dispatch; caller receives the structured error from H5.
  - GPU-with-GPU tie-break still works when multiple nodes have M.
- **Tests:**
  - Update/extend `tests/test_router.py`: GPU-no-model vs CPU-with-model →
    CPU wins (strengthen existing test so the GPU node ACTUALLY has a GPU
    model recorded, reproducing the bug).
  - `tests/test_registry.py` — `find_nodes_for_model` returns only capability
    matches.
  - E2E: two workers, one GPU-without-model + one CPU-with-model → chat routed
    to the CPU one; requested-missing-model → error, not 500.
- **Live gate:** Steps 6–8.

## H5 — Structured, actionable "model not found" errors
- **Status:** `[ ]`
- **What:** When no node can serve a model, users get a clear error listing the
  model they asked for and the models actually available across the cluster —
  not an opaque 500.
- **Why:** `controller.py:205-219` raises 503 with generic text; a worker
  `HTTPException(500, str(e))` (`worker.py:262`) surfaces raw Ollama errors.
  First-run experience dies on model-name mismatches (`README.md:27` says
  `llama3`, install pulls `llama3.2`).
- **How:**
  - Single `ModelUnavailableError` path: controller computes union of models
    from `registry.list_nodes()` and raises `400`/`404` with
    `{"error": {"message", "model", "available_models"}}`.
  - Gateway proxies non-2xx bodies already; ensure the CLI prints the readable
    message and `sys.exit(1)` (`cli.py:117-119,131-134` measurer).
  - Worker: non-streaming failures surface `detail` as JSON error body.
- **Acceptance:**
  - `lfh chat does-not-exist "hi"` prints: model not found + available list,
    non-zero exit, HTTP status 400 or 404 (never 500).
  - Available list comes from the registry union, not a single node.
- **Tests:**
  - Controller unit: chat with missing model → 400/404 + body shape.
  - CLI (CliRunner): exit code + message for missing model.
  - E2E: stream + non-stream missing-model through gateway.
- **Live gate:** Step 8.

## H6 — Streaming never silently returns an empty 200
- **Status:** `[ ]`
- **What:** If an upstream connection fails during streaming, clients must get
  an SSE error event (and `[DONE]`), never a silent empty 200 body.
- **Why:** `gateway.py:49-50` `except httpx.ConnectError: pass` swallows the
  failure and yields nothing → client sees 200 with an empty stream. Same
  weakness in `controller.py:238-246`.
- **How:**
  - Gateway stream proxy: on ConnectError (and HTTP error), emit
    `data: {"error": {...}}\n\ndata: [DONE]\n\n`.
  - Controller proxy_sse: same treatment; mark the task failed in `task_store`.
- **Acceptance:**
  - Downstream dead mid-request → SSE error event + `[DONE]`, content-type
    stays `text/event-stream`.
  - Downstream HTTP 4xx/5xx produced at the worker → forwarded as an SSE error
    event, not a silent hang.
- **Tests:**
  - E2E (extend `tests/e2e/test_live_cluster.py`): kill the worker mid-stream
    (or use a transport that raises ConnectError) and assert error + `[DONE]`.
- **Live gate:** Steps 7, 8, 10 (resilience while streaming).

## H7 — OpenAI `usage` shape correctness
- **Status:** `[ ]`
- **What:** The chat completion response `usage` must be an object with
  `prompt_tokens` / `completion_tokens` / `total_tokens` (ints), never an int
  or `{}` default.
- **Why:** `controller.py:252-266` maps `"usage": result.get("eval_count", {})`
  — `eval_count` is an int and the default is `{}`; both violate the
  OpenAI-compatible contract.
- **How:** Map Ollama's `prompt_eval_count`/`eval_count` into the object shape;
  default zeros. Single mapping helper (SoC, DRY with gateway).
- **Acceptance:**
  - `usage` is always a dict with the three int fields.
- **Tests:**
  - Unit test of the mapping helper.
  - E2E: assert `usage` shape in `test_live_cluster.py`.
- **Live gate:** Steps 6–7.

## H8 — install.sh rework for real multi-machine onboarding
- **Status:** `[ ]`
- **What:** `install.sh` must onboard a worker that actually talks to the real
  controller: systemd unit uses the joined credentials' controller URL (H1),
  accepts `--advertise-ip` (H5b/V1 support in worker) and passes it through,
  pulls a model matching the README quickstart model name, and prints the exact
  working `lfh chat <realmodel>` commands.
- **Why:** `install.sh:168-203` hardcodes `-c $CONTROLLER_URL` defaulting to
  `localhost:8001`, pulls `llama3.2` while README says `llama3`
  (`install.sh:107`, `README.md:27`), and has no advertise-ip path.
- **How:**
  - At join time, parse `HOST:PORT:SECRET` – if `--controller-url` not passed,
    derive `http://HOST:PORT` from the join token.
  - systemd `ExecStart` uses `-c <that url>` (or relies on H1 and drops `-c`).
  - Add `--advertise-ip` passing through to `lfh worker start`.
  - Map README quickstart + installed-model names: pick the pulled model name
    and print real `lfh chat <name>` examples.
- **Acceptance:**
  - Running `install.sh --join-token ...` on a bare worker VM yields a worker
    ONLINE at the controller and the README quickstart chat command works.
  - No `localhost` for `-c` unless the operator chose it explicitly.
- **Tests:**
  - Shell-level: unit-test the token→controller-URL parse helper (bash or a
    small test harness).
  - Documented manual check list.
- **Live gate:** Steps 2–7 (full install-path onboarding on the worker VM).

## H9 — `lfh status` shows heartbeat age and offline reason
- **Status:** `[ ]`
- **What:** The status CLI shows per-node: status, hostname, GPU, models, age of
  last heartbeat, and whether a joined-but-inactive node is still `pending`.
- **Why:** Today (`cli.py:30-73`) a node stuck in `pending` or a worker that
  never heartbeated looks interchangeable with a healthy one, hiding the
  onboarding failures H1–H3 address.
- **How:** Add last-heartbeat formatting + reason column to the status renderer
  (pure function — SoC; unit-testable).
- **Acceptance:**
  - `lfh status` prints per-node heartbeat age and a `pending` marker.
- **Tests:**
  - Unit: renderer pure-function tests (online/pending/offline rows).
  - CLI: monitor a registered node, assert the human-readable age appears.
- **Live gate:** Steps 4–5 (nodes show ONLINE with recent heartbeats; a second
  joined-but-idle node shows pending).

## H10 — `lfh node join` prints correct next steps
- **Status:** `[ ]`
- **What:** After a successful join, `lfh node join` prints the controller URL
  it saved and exact next commands (`lfh worker start`), and warns if the
  saved controller URL is not reachable from stdin TTY when feasible.
- **Why:** First-run confusion; users join, then run `lfh worker start` which
  today silently targets localhost (fixed by H1 — reinforce with correct
  messaging).
- **How:** Enrich the click output (`cli.py:279-286`); a small reachability
  probe is optional/soft-fail (never blocks join).
- **Acceptance:**
  - Output contains `Controller: <url>` and `Next: lfh worker start`.
- **Tests:**
  - CLI (CliRunner): assert output lines for success and failure.
- **Live gate:** Step 3.

---

# PHASE 1 — V1 COMPLETENESS (REQUIRED FOR END GOAL)

## V1-1 — Central configuration module
- **Status:** `[ ]`
- **What:** Introduce `lfhai/config.py` as the single source of defaults for
  ports, URLs, timeouts, paths, and env-var overrides (e.g. `LFHAI_CONTROLLER`,
  `LFHAI_WORKER_PORT`, `LFHAI_DB`). Remove scattered hardcoded magic values.
- **Why:** Dozens of magic numbers/URLs across cli/controller/gateway/worker/
  registry/install; H3 needs a stable DB path; DRY.
- **How:** dataclasses/pydantic settings with env overrides; keep pure (SoC).
  Migrate H3's `controller_db_path()` here.
- **Acceptance:** Every component honors env overrides; no new magic literals.
- **Tests:** config precedence tests (env > explicit > default).
- **Live gate:** No live gate (implicit — all live steps).

## V1-2 — Structured logging
- **Status:** `[ ]`
- **What:** Consistent structured log lines (component, level, request/task id)
  across controller/worker/gateway; level configurable via env.
- **Why:** Live debugging of multi-machine issues currently requires reading
  mixed-format logs.
- **How:** shared `lfhai/logging.py` setup (DRY); wire into the three
  `run_*` entrypoints.
- **Acceptance:** All three components emit the same base format; `LFHAI_LOG`
  env controls level.
- **Tests:** log-record assertions via `caplog` for a representative path.
- **Live gate:** No live gate (implicit).

## V1-3 — Shared HTTP client factory
- **Status:** `[ ]`
- **What:** One `lfhai/http.py` client factory (timeouts, transport injection)
  used by gateway proxy, controller dispatch, worker registration/heartbeat,
  and ollama — kill duplicated inline `httpx.AsyncClient(...)` construction.
- **Why:** DRY; enables transport injection for tests (replaces
  `_dispatch_to_worker` `transport` param hacks).
- **Acceptance:** All components construct clients via the factory; tests inject
  mock transports through it.
- **Tests:** factory timeout/override unit tests; existing tests refactored to
  keep passing.
- **Live gate:** No live gate (implicit).

## V1-4 — Shared auth module
- **Status:** `[ ]`
- **What:** Extract bearer parsing + constant-time compare into
  `lfhai/auth.py`; use in controller (`_bearer_secret`) and worker
  (`_verify_worker_auth`) and registry (`_secrets_equal`).
- **Why:** DRY/SoC; currently duplicated in two files with subtly different
  logic.
- **Acceptance:** No duplicated header parsing/compare logic remains.
- **Tests:** auth helper unit tests (scheme variants, whitespace, tampering).
- **Live gate:** Step 9 (auth isolation).

## V1-5 — CLI end-to-end tests
- **Status:** `[ ]`
- **What:** Click `CliRunner` tests for `status`, `nodes`, `models`, `chat`,
  `node join`, `token create/list/revoke` against a live in-process
  controller/gateway.
- **Why:** CLI is the primary UX; currently only HTTP-level tests exist.
- **Acceptance:** Every `lfh` subcommand has at least one pass + one failure
  test.
- **Tests:** new `tests/test_cli.py`.
- **Live gate:** No live gate (implicit — CLI is used throughout scenario).

## V1-6 — Pending→online heartbeat-race handling
- **Status:** `[ ]`
- **What:** Joined nodes stay `pending` until at least one authenticated
  register + heartbeat; routing excludes pending; first heartbeat flips to
  online explicitly and is tested against concurrent register/heartbeat races.
- **Why:** `registry.register` unconditionally sets ONLINE
  (`registry.py:112`), while join sets PENDING (`controller.py:116`) — the
  race between a re-register and the intent is untested.
- **Acceptance:** A pending node is never routable; the transition is
  deterministic under concurrent calls.
- **Tests:** race-oriented async tests; router exclusion already exists —
  extend for concurrency.
- **Live gate:** Step 4–5.

## V1-7 — Task lifecycle tracking
- **Status:** `[ ]`
- **What:** Tasks record terminal state transitions cleanly (dispatched →
  running → completed/failed) including streaming completes; failed tasks keep
  the error; `GET /api/v1/tasks/{id}` reflects real state.
- **Why:** `controller.py` updates tasks only on some paths; streaming never
  marks completion.
- **Acceptance:** Every dispatch path ends in completed or failed with data.
- **Tests:** task-store state-machine unit tests; e2e asserts final task record.
- **Live gate:** Steps 6–8.

## V1-8 — Detailed health/readiness across services
- **Status:** `[ ]`
- **What:** `/health` on controller, worker, gateway reports component deps
  (controller→DB, worker→ollama, gateway→controller) and recent heartbeat/task
  counts where relevant; used by the live harness for readiness waits.
- **Why:** The harness needs a cheap, truthful readiness probe (today worker
  `/health` is the only one that checks Ollama and it's bool-only).
- **Acceptance:** Each `/health` JSON includes dependency booleans; harness
  uses them.
- **Tests:** health endpoint assertions per service.
- **Live gate:** Steps 4–5 (readiness waits use `/health`).

---

# PHASE 2 — V2 NETWORKING (ROADMAP, NOT REQUIRED FOR THIS END GOAL)

- **V2-1** — Tailcat real-binary integration: worker→controller traffic through
  `tc...` tunnels, tested live with the real tailcat binary on the 2 VMs.
- **V2-2** — Controller restart recovery: `_node_secrets` re-learned from
  heartbeat/register; dispatch succeeds after controller restart without
  restarting workers.
- **V2-3** — Worker restart resync without re-join (same node_id, secret
  preserved; dedupe on register).
- **V2-4** — advertise-ip / custom port / mesh-URL overrides honored by every
  component and the harness.

# PHASE 3 — INTELLIGENCE (ROADMAP, NOT REQUIRED FOR THIS END GOAL)

- DAG / multi-step prompt scheduling; semantic caching; RAG + embeddings;
  dashboard; Android/Termux node; guardrails.

---

## END-GOAL NODES (quick reference)

Required before the loop may stop:

- [ ] **Phase 0:** H1 H2 H3 H4 H5 H6 H7 H8 H9 H10
- [ ] **Phase 1:** V1-1 V1-2 V1-3 V1-4 V1-5 V1-6 V1-7 V1-8
- [ ] **END-GOAL live scenario green** (`LIVE_TESTING.md §5`)