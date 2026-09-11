import { CodeBlock, InlineCode } from "@/components/CodeBlock";
import { TerminalBlock } from "@/components/TerminalBlock";
import { InstallCommand } from "@/components/InstallCommand";
import { Callout } from "@/components/Callout";

export default function QuickstartPage() {
  return (
    <div className="doc-content">
      <h1>Quickstart</h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-300">
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
      <InstallCommand label="Machine 1 & 2" />

      <h2>Step 2: Start the Controller</h2>
      <p>
        On the machine that will coordinate the cluster (any machine works):
      </p>
      <TerminalBlock command="lfh controller" label="Controller machine" />

      <Callout type="info">
        The controller doesn't need a GPU. It handles routing and node
        management only.
      </Callout>

      <h2>Step 3: Create a Join Token</h2>
      <p>
        Still on the controller machine, mint a join token:
      </p>
      <TerminalBlock command="lfh token create" label="Controller machine" />
      <p>
        The token carries the controller address <em>and</em> a secret, so no IP
        finding or port configuration is needed. It expires in one hour and can
        only be used once.
      </p>

      <h2>Step 4: Join Each Machine</h2>
      <p>
        On each machine that will run inference, paste the command exactly as
        printed. Replace <code>&lt;token&gt;</code> with your token:
      </p>
      <TerminalBlock
        command="lfh node join <token>"
        label="Every worker machine"
      />

      <p>
        The machine is now admitted to the cluster and its credential is saved
        locally (<code>~/.lfhai/credentials.json</code>). It is the only step
        that requires the token &mdash; the worker daemon reuses the saved
        credential from now on.
      </p>

      <h2>Step 5: Start a Worker</h2>
      <p>
        On each machine that just joined, start the worker:
      </p>
      <TerminalBlock command="lfh worker start" label="GPU machine" />

      <p>The worker will:</p>
      <ul>
        <li>Load the saved node identity and credential</li>
        <li>Detect your hardware (GPU, CPU, RAM)</li>
        <li>Query Ollama for available models</li>
        <li>Register with the controller</li>
        <li>Start sending heartbeats every 3 seconds</li>
      </ul>

      <h2>Step 6: Check Cluster Status</h2>
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

      <h2>Step 7: Send Your First Request</h2>
      <TerminalBlock
        command='lfh chat llama3.2 "What is the capital of France?"'
        label="Any machine"
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
        To add another worker (e.g., a CPU-only machine), mint a fresh token on
        the controller, run <code>lfh node join &lt;token&gt;</code> on the new
        machine, then start its worker:
      </p>
      <TerminalBlock command="lfh token create" label="Controller machine" />
      <TerminalBlock command="lfh node join <token>" label="New machine" />
      <TerminalBlock command="lfh worker start" label="New machine" />

      <p>
        The controller automatically detects the new node and starts routing
        tasks to it. Each join token is single-use, so every machine needs its
        own.
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
