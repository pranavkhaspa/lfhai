import { CodeBlock } from "@/components/CodeBlock";
import { Callout } from "@/components/Callout";

export default function ArchitecturePage() {
  return (
    <div className="doc-content">
      <h1>Architecture</h1>
      <p className="text-lg text-neutral-600 dark:text-neutral-400">
        How lfhai coordinates heterogeneous hardware into a unified AI
        inference system.
      </p>

      <h2>Overview</h2>
      <p>
        lfhai uses a controller-worker architecture. A central controller
        manages node state and routes requests. Workers run on each machine
        and interface with Ollama to execute inference tasks.
      </p>

      <CodeBlock
        code={`┌─────────────────────────────────────────────────┐
│                   User Request                   │
│          POST /v1/chat/completions               │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              Gateway (:8000)                     │
│         OpenAI-compatible HTTP API               │
│         Rate limiting, request validation        │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│            Controller (:8001)                    │
│  ┌──────────────┐  ┌──────────────┐             │
│  │   SQLite      │  │    Router    │             │
│  │   Registry    │──│  (GPU-first) │             │
│  └──────────────┘  └──────┬───────┘             │
│                           │                      │
└───────────────────────────┼──────────────────────┘
                            │
                ┌───────────┼───────────┐
                │           │           │
                ▼           ▼           ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   Worker A       │ │   Worker B       │ │   Worker C       │
│   (:8002)        │ │   (:8002)        │ │   (:8002)        │
│   GPU: RTX 3060  │ │   GPU: None      │ │   GPU: GT 710    │
│   Models: llama3 │ │   Models: whisper│ │   Models: mistral│
│        │         │ │        │         │ │        │         │
│        ▼         │ │        ▼         │ │        ▼         │
│   Ollama         │ │   Ollama         │ │   Ollama         │
│   (:11434)       │ │   (:11434)       │ │   (:11434)       │
└──────────────────┘ └──────────────────┘ └──────────────────┘`}
        language="text"
      />

      <h2>Components</h2>

      <h3>Gateway</h3>
      <p>
        The gateway is the user-facing entry point. It exposes an
        OpenAI-compatible HTTP API on port 8000. It handles request validation,
        error formatting, and proxies requests to the controller.
      </p>
      <ul>
        <li>Port: 8000 (configurable)</li>
        <li>Protocol: HTTP/1.1, HTTP/2</li>
        <li>Supports streaming (SSE) and non-streaming responses</li>
      </ul>

      <h3>Controller</h3>
      <p>
        The controller is the cluster coordinator. It manages the node registry,
        tracks heartbeats, and routes tasks to the best available worker.
      </p>
      <ul>
        <li>Port: 8001 (configurable)</li>
        <li>Storage: SQLite (no external database needed)</li>
        <li>Heartbeat timeout: 10 seconds (3 missed heartbeats)</li>
        <li>Background task: marks stale nodes offline every 5 seconds</li>
      </ul>

      <h3>Worker</h3>
      <p>
        The worker daemon runs on each machine in the cluster. It detects
        hardware capabilities, queries Ollama for available models, and executes
        inference tasks.
      </p>
      <ul>
        <li>Port: 8002 (configurable)</li>
        <li>Heartbeat interval: 3 seconds</li>
        <li>Auto-detects GPU via nvidia-smi</li>
        <li>Reports CPU, memory, disk, and GPU metrics</li>
      </ul>

      <h2>Request Flow</h2>
      <ol>
        <li>
          <strong>User sends request</strong> &mdash; POST to gateway or
          controller at <code>/v1/chat/completions</code>
        </li>
        <li>
          <strong>Controller routes</strong> &mdash; Queries SQLite for nodes
          with the requested model, picks the best one (GPU preferred)
        </li>
        <li>
          <strong>Task dispatched</strong> &mdash; Controller forwards the
          request to the selected worker's HTTP endpoint
        </li>
        <li>
          <strong>Worker executes</strong> &mdash; Proxies the request to local
          Ollama, streams or collects the response
        </li>
        <li>
          <strong>Response returned</strong> &mdash; Flows back through
          controller to gateway to user
        </li>
      </ol>

      <h2>Routing Algorithm</h2>
      <p>
        The router uses a simple heuristic to select the best node:
      </p>
      <ol>
        <li>Filter to online nodes (heartbeat not expired)</li>
        <li>
          Find nodes with the requested model in their capabilities
        </li>
        <li>If multiple found, prefer nodes with GPUs</li>
        <li>Among GPU nodes, prefer more memory</li>
        <li>Fallback to any online node if no exact match</li>
      </ol>

      <h2>Heartbeat Protocol</h2>
      <p>
        Each worker sends a heartbeat to the controller every 3 seconds with
        current metrics:
      </p>
      <CodeBlock
        code={`{
  "node_id": "worker-gpu-host-8002",
  "timestamp": 1726000000,
  "metrics": {
    "cpu_usage_pct": 45.2,
    "memory_used_bytes": 8589934592,
    "memory_total_bytes": 17179869184,
    "gpu_usage_pct": 82.0,
    "gpu_vram_used_bytes": 10737418240,
    "gpu_temp_celsius": 68.0,
    "disk_free_bytes": 240518172672
  }
}`}
        language="json"
        filename="heartbeat.json"
      />

      <p>
        If a node misses 3 consecutive heartbeats (10 seconds), the controller
        marks it offline and stops routing tasks to it.
      </p>

      <h2>Networking</h2>

      <h3>V1: Direct HTTP</h3>
      <p>
        In V1, all components communicate via plain HTTP on the LAN. This is
        simple and works for machines on the same network.
      </p>

      <h3>V2: Tailcat Tunnels</h3>
      <p>
        For nodes on different networks, lfhai includes a tailcat integration
        that creates encrypted WireGuard tunnels without requiring Tailscale
        accounts.
      </p>

      <Callout type="info">
        Tailcat provides end-to-end encrypted tunnels using WireGuard. No data
        leaves your machines unencrypted. No accounts or subscriptions required.
      </Callout>

      <h2>Data Storage</h2>
      <p>
        The controller uses SQLite for all state. No external database is
        required.
      </p>
      <ul>
        <li>
          <code>nodes</code> table &mdash; registered nodes, resources,
          capabilities, last heartbeat
        </li>
        <li>
          <code>tasks</code> table &mdash; task tracking, status, assigned
          node, results
        </li>
      </ul>

      <CodeBlock
        code={`-- Node registry schema
CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,
    hostname TEXT NOT NULL,
    ip TEXT DEFAULT '',
    status TEXT DEFAULT 'online',
    cores INTEGER DEFAULT 0,
    memory_total_bytes INTEGER DEFAULT 0,
    gpu_model TEXT DEFAULT '',
    gpu_vram_bytes INTEGER DEFAULT 0,
    has_gpu INTEGER DEFAULT 0,
    capabilities TEXT DEFAULT '[]',
    registered_at REAL NOT NULL,
    last_heartbeat REAL NOT NULL
);

-- Task tracking schema
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    assigned_node TEXT DEFAULT '',
    messages TEXT DEFAULT '[]',
    result TEXT DEFAULT '',
    error TEXT DEFAULT '',
    created_at REAL NOT NULL,
    started_at REAL DEFAULT 0,
    completed_at REAL DEFAULT 0
);`}
        language="sql"
        filename="schema.sql"
      />
    </div>
  );
}
