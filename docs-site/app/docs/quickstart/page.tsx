import { CodeBlock, InlineCode } from "@/components/CodeBlock";
import { TerminalBlock } from "@/components/TerminalBlock";
import { Callout } from "@/components/Callout";

export default function QuickstartPage() {
  return (
    <div className="doc-content">
      <h1>Quickstart</h1>
      <p className="text-lg text-neutral-600 dark:text-neutral-400">
        Get lfhai running on two machines in under 5 minutes.
      </p>

      <h2>Prerequisites</h2>
      <ul>
        <li>Two machines on the same network (or with tailcat configured)</li>
        <li>Python 3.10+ on both machines</li>
        <li>Ollama installed on at least one machine with a GPU</li>
      </ul>

      <h2>Step 1: Install lfhai</h2>
      <p>On both machines, install lfhai:</p>
      <TerminalBlock
        command="curl -fsSL https://lfhai.dev/install.sh | bash"
        label="Machine 1 & 2"
        variant="install"
      />

      <h2>Step 2: Start the Controller</h2>
      <p>
        On the machine that will coordinate the cluster (any machine works):
      </p>
      <TerminalBlock
        command="lfh controller"
        label="Controller machine"
        variant="highlight"
      />

      <p>
        The controller starts on <code>:8001</code> by default. Note the IP
        address of this machine.
      </p>

      <Callout type="info">
        The controller doesn't need a GPU. It handles routing and node
        management only.
      </Callout>

      <h2>Step 3: Start a Worker</h2>
      <p>
        On each machine that will run inference (the GPU machine):
      </p>
      <TerminalBlock
        command="lfh worker start -c http://<controller-ip>:8001"
        label="GPU machine"
        variant="highlight"
      />

      <p>The worker will:</p>
      <ul>
        <li>Detect your hardware (GPU, CPU, RAM)</li>
        <li>Query Ollama for available models</li>
        <li>Register with the controller</li>
        <li>Start sending heartbeats every 3 seconds</li>
      </ul>

      <h2>Step 4: Check Cluster Status</h2>
      <TerminalBlock
        command="lfh status"
        label="Any machine"
      />

      <p>You should see output like:</p>
      <CodeBlock
        code={`Gateway:     ok
  Controller: connected
Controller:  ok

Nodes (1):
  a1b2c3d4e5f6  online  gpu-host [NVIDIA GeForce RTX 3060] models=['llama3.2']`}
        language="text"
      />

      <h2>Step 5: Send Your First Request</h2>
      <TerminalBlock
        command='lfh chat llama3.2 "What is the capital of France?"'
        label="Any machine"
        variant="highlight"
      />

      <p>Or use curl directly:</p>
      <CodeBlock
        code={`curl -X POST http://<controller-ip>:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "llama3.2",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'`}
        language="bash"
      />

      <h2>Step 6: Stream Responses</h2>
      <CodeBlock
        code={`# Using the CLI
lfh chat --stream llama3.2 "Tell me a joke"

# Using curl
curl -X POST http://<controller-ip>:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Tell me a joke"}],
    "stream": true
  }'`}
        language="bash"
      />

      <h2>Adding More Nodes</h2>
      <p>
        To add another worker (e.g., a CPU-only machine), just run the worker
        command on it:
      </p>
      <TerminalBlock
        command="lfh worker start -c http://<controller-ip>:8001"
        label="Additional machine"
      />

      <p>
        The controller will automatically detect the new node and start routing
        tasks to it.
      </p>

      <h2>What's Next?</h2>
      <ul>
        <li>
          <a href="/docs/architecture">Architecture</a> &mdash; understand how
          lfhai works under the hood
        </li>
        <li>
          <a href="/docs/cli">CLI Reference</a> &mdash; all available commands
        </li>
        <li>
          <a href="/docs/api">API Reference</a> &mdash; HTTP endpoints for
          programmatic access
        </li>
        <li>
          <a href="/docs/configuration">Configuration</a> &mdash; customize
          ports, URLs, and behavior
        </li>
      </ul>
    </div>
  );
}
