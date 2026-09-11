import { CodeBlock, InlineCode } from "@/components/CodeBlock";
import { Callout } from "@/components/Callout";

export default function APIPage() {
  return (
    <div className="doc-content">
      <h1>API Reference</h1>
      <p className="text-lg text-neutral-600 dark:text-neutral-400">
        HTTP endpoints for programmatic access to lfhai.
      </p>

      <h2>Gateway Endpoints</h2>
      <p>
        The gateway exposes an OpenAI-compatible API. Default port:{" "}
        <code>:8000</code>.
      </p>

      <h3>POST /v1/chat/completions</h3>
      <p>
        Submit a chat completions request. Compatible with the OpenAI API
        format.
      </p>

      <CodeBlock
        code={`{
  "model": "llama3.2",
  "messages": [
    {"role": "user", "content": "What is the capital of France?"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 2048
}`}
        language="json"
        filename="request.json"
      />

      <p>Response:</p>
      <CodeBlock
        code={`{
  "id": "chatcmpl-a1b2c3d4",
  "object": "chat.completion",
  "model": "llama3.2",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {}
}`}
        language="json"
        filename="response.json"
      />

      <h3>POST /v1/chat/completions (Streaming)</h3>
      <p>
        Set <code>"stream": true</code> to receive Server-Sent Events (SSE).
      </p>

      <CodeBlock
        code={`data: {"choices":[{"delta":{"content":"The"}}]}
data: {"choices":[{"delta":{"content":" capital"}}]}
data: {"choices":[{"delta":{"content":" of"}}]}
data: {"choices":[{"delta":{"content":" France"}}]}
data: {"choices":[{"delta":{"content":" is"}}]}
data: {"choices":[{"delta":{"content":" Paris."}}]}
data: [DONE]`}
        language="text"
        filename="stream.txt"
      />

      <h3>GET /v1/models</h3>
      <p>List all available models across the cluster.</p>

      <CodeBlock
        code={`{
  "object": "list",
  "data": [
    {"id": "llama3.2", "object": "model", "owned_by": "lfhai"},
    {"id": "whisper", "object": "model", "owned_by": "lfhai"}
  ]
}`}
        language="json"
      />

      <h3>GET /v1/nodes</h3>
      <p>List all registered nodes in the cluster.</p>

      <h3>GET /health</h3>
      <p>Gateway health check.</p>
      <CodeBlock code={`{"status": "ok", "controller": "connected"}`} language="json" />

      <h2>Controller Endpoints</h2>
      <p>
        The controller manages nodes and routes tasks. Default port:{" "}
        <code>:8001</code>.
      </p>

      <h3>POST /api/v1/nodes/register</h3>
      <p>Register a new worker node.</p>
      <CodeBlock
        code={`{
  "node_id": "worker-gpu-host-8002",
  "hostname": "gpu-host",
  "resources": {
    "ip": "192.168.1.105",
    "cores": 8,
    "memory_total_bytes": 17179869184,
    "gpu": {
      "model": "NVIDIA GeForce RTX 3060",
      "vram_total_bytes": 12884901888,
      "cuda_version": "12.2"
    }
  },
  "capabilities": {
    "models": ["llama3.2", "mistral"],
    "has_gpu": true,
    "has_cuda": true
  }
}`}
        language="json"
        filename="register.json"
      />

      <h3>POST /api/v1/nodes/heartbeat</h3>
      <p>Send heartbeat telemetry from a worker.</p>
      <CodeBlock
        code={`{
  "node_id": "worker-gpu-host-8002",
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

      <h3>GET /api/v1/nodes</h3>
      <p>List all registered nodes.</p>

      <h3>GET /api/v1/nodes/:node_id</h3>
      <p>Get details for a specific node.</p>

      <h3>DELETE /api/v1/nodes/:node_id</h3>
      <p>Remove a node from the registry.</p>

      <h3>POST /v1/chat/completions</h3>
      <p>
        Route a chat request to the best worker (same as gateway endpoint, but
        directly on the controller).
      </p>

      <h3>GET /api/v1/tasks/:task_id</h3>
      <p>Get task status and result.</p>

      <h2>Worker Endpoints</h2>
      <p>
        The worker exposes local task execution endpoints. Default port:{" "}
        <code>:8002</code>.
      </p>

      <h3>GET /worker/status</h3>
      <p>Worker status and capabilities.</p>
      <CodeBlock
        code={`{
  "node_id": "worker-gpu-host-8002",
  "status": "online",
  "models": ["llama3.2", "mistral"],
  "ollama_url": "http://localhost:11434"
}`}
        language="json"
      />

      <h3>POST /worker/task</h3>
      <p>Execute an inference task via Ollama.</p>
      <CodeBlock
        code={`{
  "model": "llama3.2",
  "messages": [{"role": "user", "content": "Hello!"}],
  "stream": false,
  "temperature": 0.7
}`}
        language="json"
        filename="task.json"
      />

      <h3>GET /health</h3>
      <p>Worker health check (includes Ollama connectivity).</p>
      <CodeBlock code={`{"status": "ok", "ollama": true}`} language="json" />

      <h2>Error Responses</h2>
      <p>All endpoints return standard HTTP error codes:</p>
      <CodeBlock
        code={`{
  "detail": "No nodes available for model 'llama3'. Register a worker with this model first."
}`}
        language="json"
      />

      <table>
        <thead>
          <tr>
            <th>Code</th>
            <th>Meaning</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>200</td>
            <td>Success</td>
          </tr>
          <tr>
            <td>404</td>
            <td>Node or task not found</td>
          </tr>
          <tr>
            <td>500</td>
            <td>Internal error (inference failed)</td>
          </tr>
          <tr>
            <td>503</td>
            <td>No nodes available or controller unreachable</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
