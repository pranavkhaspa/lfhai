# INSTRUCTIONS.md — The Loop Driver

> **Read this file in FULL at the start of every iteration.** It is the master
> contract for the automated development loop. The docs it references are
> `checklist.md` (what to build), `context.md` (project state), and
> `LIVE_TESTING.md` (how to prove it works). This loop runs in **auto-approval
> mode**: every command you issue is approved automatically. That is why the
> scope rules below are absolute and must be obeyed by the agent itself.

---

## 0. THE END GOAL

The loop terminates **only** when BOTH are true:

1. **Every checklist item in `checklist.md` marked as `REQUIRED FOR END GOAL` is
   checked off (`[x]`).** That means it passed the full pipeline: implemented →
   tests → lint → AI review → code review → **live 2-VM test** → docs updated.
2. **The END-GOAL scenario in `LIVE_TESTING.md` (§5) passes GREEN end-to-end**
   on two real qemu VMs. "Green" means every numbered step in the scenario
   produced the exact asserted output with no manual workaround.

If the END-GOAL check fails at any point, the loop **must not stop**. It picks
the next item that explains the failure (usually the earliest unchecked Phase 0
item) and drives it through the pipeline.

---

## 1. FILESYSTEM SCOPE (ABSOLUTE — NEVER VIOLATE)

Auto-approval mode means no permission prompt will stop you. You are therefore
**personally responsible** for staying inside these boundaries:

### ALLOWED
| Path | What for |
|---|---|
| `/home/pro/lfhai` (and any subdirectory) | The lfhai repo — read, edit, test. This is your only code workspace. |
| `/home/pro/multipass` | The qemu VM harness — VM scripts, cloud images, logs. You may READ, EDIT scripts, CREATE new helper scripts, and write VM logs here. |
| **Inside the two VMs over SSH** | Guest filesystems (`~`, `/opt`, `/etc` for the lfhai/ollama services you install) are fair game. Installing packages **inside the VMs** (apt, pip, curl) is allowed. |
| The transient temp dir under `/tmp` (e.g. `/tmp/opencode`) | Scratch space for builds and test artifacts. |

### FORBIDDEN
| Thing | Consequence |
|---|---|
| Any host path outside `/home/pro/lfhai`, `/home/pro/multipass`, `/tmp/opencode` | Hard stop. Do not read, write, or `cd` there. |
| Editing `~/.ssh`, host `crontab`, host `systemd units`, host network config, host firewall | Hard stop. |
| Host package managers / host system-level installs (`apt`, `snap`, `brew` on the host) | Hard stop. Do not install anything on the host. (Inside VMs it is allowed.) |
| `git push`, `git remote`, creating public artifacts, publishing the wheel | Hard stop unless a checklist item explicitly instructs otherwise (none currently do). |
| Destructive edits to the base images: `noble-server-cloudimg-amd64.img` / `seed.img` | Hard stop. If you need a clean slate, COPY them first (see `LIVE_TESTING.md` §4 Reset). |
| Leaving running processes / VMs / servers behind after finishing | Clean up what you started, or document exactly what is still running in `context.md`. |

### IF A TASK NEEDS SOMETHING OUT OF SCOPE
1. Mark the checklist item `[BLOCKED <reason>]`.
2. Append a `BLOCKED:` entry to the worklog in `context.md` with the exact
   out-of-scope need.
3. STOP. Do not improvise an alternative outside scope. Report.

> The two VMs themselves are "machines". Anything INSIDE them is in scope.
> The host is only a thin launchpad: `~/multipass` scripts + ssh into guests.

---

## 2. ITERATION RULES

1. **ONE item per iteration.** Pick the first unchecked item in
   `checklist.md` (items are ordered; earlier items unblock later ones).
   Finish it completely before moving to the next.
2. **No batching.** Do not implement two checklist items in one pass.
3. **No scope creep.** A single iteration must be a cohesive, reviewable
   change. Unrelated refactors belong in their own checklist item.
4. **Re-read state each iteration.** `context.md` and `checklist.md` are the
   only truth. Re-read them at the top of every iteration — another agent may
   have updated them between runs.
5. **Keep `context.md` honest.** After every iteration, update it: test count,
   versions, what is running, what changed, current findings.
6. **Never mark anything done early.** The rules in §4 are immutable.

---

## 3. THE PER-ITEM PIPELINE

For the single chosen item, perform these steps **in order**. Do not skip.

### Step 1 — Restate the item
Write one sentence in the `context.md` worklog: what you are doing and why.
Example: `2026-09-22 — H1: making the worker beacon to the controller recorded
in its credentials.json so install.sh nodes stop talking to localhost.`

### Step 2 — Design note (before any code)
Add a short "Design" subsection to the checklist item (or the worklog) that
names:
- the modules/files to touch,
- the SOLID / Separation-of-Concerns / DRY mapping,
- the acceptance criteria it maps to.

Keep it tiny (2–6 lines). It proves you thought before typing.

### Step 3 — Implement
- Small, cohesive change. No unrelated edits.
- Follow existing style. Python 3.10+ compatible (pyproject requires ≥3.10;
  CI tests 3.10 and 3.13 — avoid 3.11+-only syntax).
- Use the existing patterns already in the repo (Pydantic models, httpx,
  FastAPI, aiosqlite). Do not introduce new dependencies unless a checklist
  item requires it.
- Do NOT add comments unless they explain a non-obvious "why". Keep code
  self-documenting.

### Step 4 — Tests (mandatory, thorough)
Write or update tests for **every** behavior of the change:
- happy path,
- error path(s),
- unauthorized / auth-mismatch path,
- boundary / edge cases,
- a **regression test** that reproduces the exact bug the item fixes (it must
  fail on the old code and pass on the new code).

Follow the existing layout: unit tests under `tests/`, live-stack tests under
`tests/e2e/`. Async tests use `pytest.mark.asyncio` (asyncio_mode=auto is set).
Never share mutable global state across tests; use tmp files or `:memory:` DBs
and clean up servers in `finally` blocks (see `tests/e2e/test_multi_node.py`).

### Step 5 — Verify (must all pass before moving on)
```bash
ruff check lfhai/ tests/
ruff format --check lfhai/ tests/        # do NOT leave unformatted code
python -m pytest tests/ -q               # full suite, must be green
```
Fix anything that fails. Do not silence failures with `noqa` or skips unless
you document why in the item.

### Step 6 — AI self-review (fixed checklist)
Answer each question honestly against your own diff:
1. **Auth/security:** any new endpoint or request path — is it authenticated
   where the system requires it? Are secrets ever logged/printed? Constant-time
   compares used?
2. **Error paths:** every `except` either recovers meaningfully, propagates a
   structured error, or is documented. No silent `except: pass` that swallows
   a real failure (this repo has a known one — see H6).
3. **Concurrency/races:** async code — any shared-state mutation across tasks?
   Any start-before-register ordering hazards (see H2)? Any loop that can spin
   forever?
4. **Resource cleanup:** clients closed, subprocesses terminated, servers
   stopped in `finally`, DB connections closed in tests.
5. **API contract:** JSON shapes match the documented contract
   (`README.md` API tables, OpenAI-compatible shapes). No int-where-object
   mistakes (see H7).
6. **DRY / SoC:** did you duplicate logic that already lives elsewhere? If the
   change adds a 3rd copy of something, put it in `lfhai/config.py` /
   an appropriate shared module instead.
7. **Dead code:** no unused imports, functions, or flags left behind.
8. **Compatibility:** code must run on Python 3.10+ and pass the existing test
   suite untouched (no breaking other tests to make yours pass).

### Step 7 — Code review
- `git diff` the change. Verify it is minimal and cohesive, no unrelated edits.
- Read the diff as a reviewer would: does each hunk make sense? Any leftover
  debug prints, TODO stubs, or commented-out code? Remove them.
- Double-check the files *affected indirectly* (README, docs-site, install.sh,
  cli.py) still agree with the change.

### Step 8 — Live 2-VM test
If the item has any "Live gate" steps listed in `checklist.md`, run those
steps using the harness in `LIVE_TESTING.md`. Paste the real output (trimmed)
into the `context.md` worklog. The item is not done until the live gate passes.

### Step 9 — Update docs
- Update `README.md` if user-facing behavior changed (commands, endpoints,
  flags, defaults).
- Update `context.md`: state, versions, test count, worklog, findings.
- Update the checklist item: mark `[x]`, set the completion date, and write a
  one-line summary of what shipped.

### Step 10 — Confirm & continue
- Run the full pipeline verification once more (§4 checks).
- Your iteration is complete. Loop again: it is time for the next item.

---

## 4. DEFINITION OF DONE

A checklist item is `[x]` **only** when ALL are true:

- [ ] Implemented exactly as scoped (no leftover TODOs).
- [ ] Tests written covering happy/error/auth/boundary + regression; suite green.
- [ ] `ruff check` and `ruff format --check` clean.
- [ ] AI self-review checklist answered with no open "no" items.
- [ ] Code review of the diff done; diff is minimal.
- [ ] Live 2-VM gate steps passed (real harness output in worklog) — or the
      item has no live gate and a `No live gate` note.
- [ ] README/context/checklist updated consistently.

If any checkbox is false, the item is **NOT done**. Either keep working on it
or mark it `[BLOCKED]` per §1.

---

## 5. STATUS MARKERS (used in checklist.md)

| Marker | Meaning |
|---|---|
| `[ ]` | Not started. |
| `[~]` | In progress (current iteration). Only one item may be `[~]` at a time. |
| `[x]` | Done — passed the full Definition of Done above. |
| `[BLOCKED <reason>]` | Cannot proceed; out-of-scope or hard blocker. Loop: see §1. |
| `[x] (no live gate)` | Done; the item intentionally has no live-test steps. |

---

## 6. FREQUENTLY NEEDED FACTS (cheat-sheet)

- Package: `lfhai`, entry point `lfh` (click). Components: gateway :8000,
  controller :8001, worker :8002, Ollama :11434.
- Controllers/CLI default DB: `lfhai.db` in CWD today — **H3 will move it** to
  a stable path; after H3 lands, use `~/.lfhai/controller.db`.
- Credentials: `~/.lfhai/credentials.json` `{controller, node_id, node_secret}`
  mode 0600. Worker `-c` currently defaults to localhost — **H1 fixes that**.
- Install & test:
  ```bash
  pip install -e ".[dev]"
  ruff check lfhai/ tests/
  python -m pytest tests/ -q
  ```
- This loop is Python-biased; the qemu/VM scripts in `~/multipass` are bash
  and may be edited freely (in scope).
- The repo contains a `docs-site/` Next.js site. Only touch it when a checklist
  item or README consistency demands it (keep it in sync, do not redesign).