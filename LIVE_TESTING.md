# LIVE_TESTING.md — Two-Machine Verification Harness

> The proof layer of the loop. Every checklist item with a "Live gate" is
> verified here on **two real qemu VMs** (the same KVM/user-mode-networking
> pattern as the existing `~/multipass/start-vm.sh`, extended to two
> machines). The END-GOAL scenario in **§5** is the acceptance test the loop
> must leave green.
>
> Scope reminder (`instructions.md §1`): you may edit/create scripts under
> `~/multipass` on the host and run anything inside the two VMs over SSH. Do
> NOT install host-side tools; reuse the existing `seed.img`; never mutate the
> base image (`noble-server-cloudimg-amd64.img`) in place.

---

## 1. Topology

```
                         HOST  (launchpad, pro@pro)
   ┌─────────────────────────────────────────────────────────────┐
   │  qemu VM 1 = vm-controller   ssh host :2222 -> guest 22     │
   │            hostfwd 8000->8000   8001->8001                   │
   │                                                              │
   │  qemu VM 2 = vm-worker      ssh host :2223 -> guest 22      │
   │            hostfwd 8002->8002                                │
   └─────────────────────────────────────────────────────────────┘
      guest gw = 10.0.2.2 (host/slirp)   guest ip = 10.0.2.15 (each)
```

| From | To where | Path used | Why |
|---|---|---|---|
| vm-worker | controller | `http://10.0.2.2:8001` | worker beacons/joins a URL reachable through the host (slirp hostfwd → vm-controller:8001) |
| vm-controller | worker | `http://10.0.2.2:8002` | worker advertises `--advertise-ip 10.0.2.2`; controller dispatches via hostfwd → vm-worker:8002 |
| host | vm-controller | `http://localhost:8001` or `:8000` | convenience probes |
| host | either VM | `ssh -p 2222/2223 <user>@localhost` | administer |

> Why `10.0.2.2`? QEMU's `-netdev user` gives every guest the same subnet:
> itself = `10.0.2.15`, host/gateway = `10.0.2.2`. A guest connecting to
> `10.0.2.2:<hostfwd-port>` reaches the host's forwarded listener, which is
> another VM's qemu process — so the two VMs talk through the host without any
> host-side proxy. Verify this with the cross-connectivity probe in Step 1
> before trusting anything else.

## 2. Assets in `~/multipass`

| File | Role |
|---|---|
| `noble-server-cloudimg-amd64.img` | Ubuntu 24.04 cloud image (base, READ-ONLY; qcow2 despite the `.img` name) |
| `seed.img` | cloud-init seed (user-data: user + ssh key). Reused by BOTH VMs as-is. |
| `start-vm.sh` | parametrized launcher (below) — supersedes the single-VM original but keeps its defaults |
| `provision-controller.sh`, `provision-worker.sh` | one-time VM provisioning |
| `run-scenario.sh` | the END-GOAL scenario driver (§5) |
| `vm-*.qcow2` | per-VM COW overlays (created on demand, disposable) |

`VM_USER` = the user that cloud-init creates (check `seed.img` config; default
`ubuntu`). Everything below uses `VM_USER=ubuntu` — adjust if your seed differs.

## 3. VM lifecycle

### 3.1 `~/multipass/start-vm.sh` (replaces the original 1-VM script)

```bash
#!/usr/bin/env bash
# Start one lfhai test VM behind user-mode networking.
# Usage: bash start-vm.sh [name] [ssh_host_port] [fwd_ports_csv] [ram_mb] [smp]
#   bash start-vm.sh                       # vm-default, ssh :2222, 4G (== original script)
#   bash start-vm.sh vm-controller 2222 8000,8001 4096 2
#   bash start-vm.sh vm-worker     2223 8002     2048 2
set -euo pipefail
NAME="${1:-default}"
SSH_HP="${2:-2222}"
FWD_CSV="${3:-}"
RAM="${4:-4096}"
SMP="${5:-2}"
cd ~/multipass
BASE_IMG="${BASE_IMG:-noble-server-cloudimg-amd64.img}"
SEED_IMG="${SEED_IMG:-seed.img}"

FMT="$(qemu-img info --output=json "$BASE_IMG" | python3 -c 'import sys,json;print(json.load(sys.stdin)["format"])')"
if [ "$FMT" = "qcow2" ]; then
  OVERLAY="vm-${NAME}.qcow2"
  [ -f "$OVERLAY" ] || qemu-img create -f qcow2 -F qcow2 -b "$BASE_IMG" "$OVERLAY"
  DRIVE="file=${OVERLAY},if=virtio"
else
  echo "WARN: base image is $FMT, no COW overlay; concurrent VMs may clash" >&2
  DRIVE="file=${BASE_IMG},if=virtio"
fi

NET="user,id=n0,hostfwd=tcp::${SSH_HP}-:22"
[ -n "$FWD_CSV" ] && for p in ${FWD_CSV//,/ }; do [ -n "$p" ] && NET="$NET,hostfwd=tcp::${p}-:${p}"; done

echo "Starting $NAME  ssh :$SSH_HP  forwards:${FWD_CSV:-none}  ram:${RAM}M"
exec qemu-system-x86_64 \
  -enable-kvm -m "$RAM" -smp "$SMP" \
  -drive "$DRIVE" \
  -drive "file=${SEED_IMG},if=virtio,format=raw" \
  -netdev "$NET" \
  -device virtio-net-pci,netdev=n0 \
  -nographic
```

Launch both (each in its own terminal / `setsid ... &`), first boot ~1-2 min:

```bash
cd ~/multipass
bash start-vm.sh vm-controller 2222 8000,8001 4096 2   # Terminal 1
bash start-vm.sh vm-worker     2223 8002     2048 2   # Terminal 2
# wait helper (host side):
for i in $(seq 1 120); do ssh -q -p 2222 ubuntu@localhost true 2>/dev/null && echo CONTROLLER-VM-UP && break; sleep 2; done
for i in $(seq 1 120); do ssh -q -p 2223 ubuntu@localhost true 2>/dev/null && echo WORKER-VM-UP && break; sleep 2; done
```

### 3.2 Provisioning — run once per fresh VM

`provision-controller.sh` (host side):

```bash
#!/usr/bin/env bash
set -euo pipefail
VM_USER=ubuntu; PORT=2222
URL="ssh://..."; scp_p(){ scp -P "$1" -r -p /home/pro/lfhai "${VM_USER}@localhost:lfhai"; }
ssh_p(){ ssh -p "$1" "${VM_USER}@localhost" "$@"; }
scp -P $PORT -r -p /home/pro/lfhai "${VM_USER}@localhost:lfhai"
ssh -P $PORT "${VM_USER}@localhost" '
  sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv python3-pip >/dev/null
  cd ~/lfhai && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"
  # until H3 lands, controller+token MUST run from ~/lfhai (CWD = DB path)
  cd ~/lfhai && nohup .venv/bin/lfh controller >~/ctrl.log 2>&1 &
  cd ~/lfhai && nohup .venv/bin/lfh gateway    >~/gw.log   2>&1 &
  for i in $(seq 1 60); do curl -sf http://localhost:8001/health >/dev/null && break; sleep 1; done
  curl -sf http://localhost:8001/health && echo CONTROLLER-READY
'
```

`provision-worker.sh` (host side) — installs Ollama + one small model:

```bash
#!/usr/bin/env bash
set -euo pipefail
VM_USER=ubuntu; PORT=2223
scp -P $PORT -r -p /home/pro/lfhai "${VM_USER}@localhost:lfhai"
ssh -P $PORT "${VM_USER}@localhost" '
  sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv python3-pip >/dev/null
  cd ~/lfhai && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"
  command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
  curl -fsSL http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || (sudo systemctl start ollama || ollama serve >~/ollama.log 2>&1 &)
  ollama pull qwen2.5:0.5b
  ollama list && echo WORKER-PROVISIONED
'
```

> Model choice: `qwen2.5:0.5b` is tiny and runs on CPU quickly. The scenario
> references `<MODEL>` everywhere — set `MODEL=qwen2.5:0.5b`.

## 4. Reset (clean slate, keep VMs running but wipe cluster state)

```bash
# in each VM: stop daemons, drop DB + credentials (fresh state)
ssh -p 2222 ubuntu@localhost 'pkill -f "lfh (controller|gateway)" || true; rm -f ~/lfhai/lfhai.db ~/.lfhai/controller.db'
ssh -p 2223 ubuntu@localhost 'pkill -f "lfh worker" || true; rm -f ~/.lfhai/credentials.json'
```

Full VM teardown (destructive; rebuild overlays):

```bash
# on host:
pkill -f "qemu-system-x86_64.*vm-controller" || true
pkill -f "qemu-system-x86_64.*vm-worker"     || true
cd ~/multipass && rm -f vm-controller.qcow2 vm-worker.qcow2
# then relaunch + re-provision (§3)
```

Never delete `noble-server-cloudimg-amd64.img` or `seed.img`.

## 5. END-GOAL SCENARIO (the acceptance test)

Execute every step in order. Each step prints `PASS` only when its assert
succeeds; any failure stops the run with the exact output captured. The
complete set green = END GOAL reached (with checklist Phase 0 + Phase 1 also
`[x]`).

Shared vars: `VM_USER=ubuntu`, `CTRL_SSH='ssh -p 2222 ubuntu@localhost'`,
`WORK_SSH='ssh -p 2223 ubuntu@localhost'`, `MODEL=qwen2.5:0.5b`.

```bash
# STEP 0 — clean slate before every gated run (no stale daemons, fresh DB)
$CTRL_SSH 'pkill -f "lfh (controller|gateway)" || true; rm -f lfhai.db; sleep 1'
$WORK_SSH 'pkill -f "lfh worker" || true; rm -f ~/.lfhai/credentials.json; sleep 1'

# STEP 1 — services up + cross-VM reachability
$CTRL_SSH 'cd ~/lfhai && nohup .venv/bin/lfh controller >~/ctrl.log 2>&1 &'
$CTRL_SSH 'cd ~/lfhai && nohup .venv/bin/lfh gateway    >~/gw.log   2>&1 &'
$CTRL_SSH 'for i in $(seq 1 60); do curl -sf localhost:8001/health && break; sleep 1; done'
# assert: worker VM can reach the controller THROUGH the host
$WORK_SSH 'curl -sf http://10.0.2.2:8001/health'   # == {"status":"ok",...}
#   FAIL here means the slirp hostfwd bridge is broken; fix topology first.

# STEP 2 — mint join token on controller VM (advertise 10.0.2.2, the reachable path)
TOKEN_LINE="$($CTRL_SSH 'cd ~/lfhai && .venv/bin/lfh token create --host 10.0.2.2' | grep -E '^.*lfh node join .*$' | tail -1)"
# TOKEN_LINE ~ "lfh node join 10.0.2.2:8001:SECRET"
TOKEN="$(echo "$TOKEN_LINE" | sed -E 's/.*join //; s/^.*://; s/ .*$//')"

# STEP 3 — worker VM joins
$WORK_SSH "cd ~/lfhai && .venv/bin/lfh node join 10.0.2.2:8001:${TOKEN}" 2>&1 | grep -q "Joined cluster"

# STEP 4 — start worker WITHOUT -c (H1 live gate) + advertise-ip
$WORK_SSH 'cd ~/lfhai && nohup .venv/bin/lfh worker start --advertise-ip 10.0.2.2 -o http://127.0.0.1:11434 >~/worker.log 2>&1 &'
# assert node ONLINE at controller within ~20s
$CTRL_SSH 'for i in $(seq 1 40); do
   "$(cd ~/lfhai && .venv/bin/lfh nodes 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(any(n[\"status\"]==\"online\" for n in d))")" && break; sleep 1; done' | grep -q True

# STEP 5 — inventory sanity
$CTRL_SSH 'cd ~/lfhai && .venv/bin/lfh status' | grep -q "online"
$CTRL_SSH 'cd ~/lfhai && .venv/bin/lfh models' | grep -q "$MODEL"
$CTRL_SSH "curl -sf http://localhost:8000/v1/models" | grep -q "$MODEL"

# STEP 6 — non-streaming chat end-to-end
OUT="$($CTRL_SSH "cd ~/lfhai && .venv/bin/lfh chat $MODEL 'Reply with exactly: PONG'")"
echo "$OUT" | grep -q "PONG"

# STEP 7 — streaming chat end-to-end (multiple chunks + [DONE], non-empty)
OUT="$($CTRL_SSH "cd ~/lfhai && .venv/bin/lfh chat --stream $MODEL 'Count: 1 2 3'")"
echo "$OUT" | grep -q "\[DONE\]" && [ "$(echo "$OUT" | wc -c)" -gt 20 ]

# STEP 8 — wrong model → structured error, never 500
$CTRL_SSH "cd ~/lfhai && .venv/bin/lfh chat this-model-does-not-exist hi; test \$? -ne 0" \
  && $CTRL_SSH "cd ~/lfhai && .venv/bin/lfh chat this-model-does-not-exist hi 2>&1" | grep -qi "$MODEL"

# STEP 9 — auth isolation on the worker
$WORK_SSH "curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8002/worker/task \
     -H 'Content-Type: application/json' -d '{\"model\":\"$MODEL\",\"messages\":[]}'" | grep -q 401
$WORK_SSH "curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8002/worker/task \
     -H 'Authorization: Bearer WRONG' -H 'Content-Type: application/json' \
     -d '{\"model\":\"$MODEL\",\"messages\":[]}'" | grep -q 401

# STEP 10 — kill worker → offline → restart → online → chat works again
$WORK_SSH 'pkill -f "lfh worker start" || true'
$CTRL_SSH 'for i in $(seq 1 20); do
   "$(cd ~/lfhai && .venv/bin/lfh nodes | python3 -c "import sys,json;print(all(n[\"status\"]!=\"online\" for n in json.load(sys.stdin)))")" && break; sleep 2; done' | grep -q True
$WORK_SSH 'cd ~/lfhai && nohup .venv/bin/lfh worker start --advertise-ip 10.0.2.2 -o http://127.0.0.1:11434 >~/worker.log 2>&1 &'
$CTRL_SSH 'for i in $(seq 1 40); do
   "$(cd ~/lfhai && .venv/bin/lfh nodes | python3 -c "import sys,json;print(any(n[\"status\"]==\"online\" for n in json.load(sys.stdin)))")" && break; sleep 1; done' | grep -q True
$CTRL_SSH "cd ~/lfhai && .venv/bin/lfh chat $MODEL 'Reply with: PONG'" | grep -q "PONG"

# STEP 11 — controller restart → worker re-heartbeats, dispatch recovers (no worker restart)
$CTRL_SSH 'pkill -f "lfh (controller|gateway)" || true; sleep 1; cd ~/lfhai && nohup .venv/bin/lfh controller >~/ctrl.log 2>&1 & cd ~/lfhai && nohup .venv/bin/lfh gateway >~/gw.log 2>&1 &'
$CTRL_SSH 'for i in $(seq 1 30); do curl -sf localhost:8001/health >/dev/null && break; sleep 1; done'
$CTRL_SSH 'for i in $(seq 1 30); do
   "$(cd ~/lfhai && .venv/bin/lfh nodes | python3 -c "import sys,json;print(any(n[\"status\"]==\"online\" for n in json.load(sys.stdin)))")" && break; sleep 1; done' | grep -q True
$CTRL_SSH "cd ~/lfhai && .venv/bin/lfh chat $MODEL 'Reply with: PONG'" | grep -q "PONG"

echo "END-GOAL SCENARIO: ALL GREEN"
```

### Mapping to checklist items

| Step(s) | Exercises |
|---|---|
| 2–3 | H3 (DB path), H10 (join UX), join-token flow |
| 4 | **H1** (worker reaches controller from credentials, no `-c`), H2 (starts before register), H8 (advertise-ip plumbing), H9 (status) |
| 5 | H9, V1-8 (health), V1-5 (CLI) |
| 6 | H4 (routing to the node with the model), H7 (usage), V1-7 (task state) |
| 7 | H6 (streaming never silent), H7 |
| 8 | H5 (structured model-not-found), H4 |
| 9 | V1-4 (shared auth), worker auth |
| 10 | H9 (offline detection), H2 (worker self-heals), V1-6 |
| 11 | controller restart resync (hardened by V2-2 later) |

## 6. Alternative: two physical machines on a LAN

Same scenario, minus slirp specifics:

1. Machine A (controller): install lfhai; `lfh controller` + `lfh gateway`.
   `lfh token create` → auto-detected LAN IP (verify it is A's LAN IP).
2. Machine B (worker): install lfhai + Ollama + small model; run the printed
   `lfh node join <A-LAN-IP>:8001:TOKEN`; `lfh worker start` (H1 picks the
   controller URL from credentials; H8's `--advertise-ip A-reachable-IP` if
   multi-homed).
3. Machines must reach each other on TCP 8000/8001/8002 (firewall/ports).
4. Run Steps 2–11 with `10.0.2.2` replaced by A's LAN IP / B's LAN IP.

## 7. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Step 1 `curl 10.0.2.2:8001` fails from worker | hostfwd not added to vm-controller (need `8000,8001`); or qemu not running; verify `ss -tlnp \| grep -E '8000|8001'` on host |
| Node never ONLINE | Worker `-c` wrong (pre-H1); controller DB path mismatch (pre-H3); check `~/worker.log`, `~/ctrl.log` in VMs |
| 401 on join | token minted in different DB than controller (H3); or expired (TTL 1h) / single-use reused |
| 500 "model not found" on chat | model name mismatch request vs installed (H4/H5); use `lfh models` to get exact name |
| port in use launching qemu | previous VM still running: `pkill -f "qemu-system-x86_64.*vm-"` or pick another host port |
| ssh "REMOTE HOST IDENTIFICATION CHANGED" | VM rebuilt with same ip/port; remove stale host key entry for `[localhost]:2222/2223` ONLY (within scope, it is our own VM testing) |
| cross-VM works one direction only | confirm BOTH hostfwd rules: 8001 on vm-controller AND 8002 on vm-worker