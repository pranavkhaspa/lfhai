import { CodeBlock, InlineCode } from "@/components/CodeBlock";
import { TerminalBlock } from "@/components/TerminalBlock";
import { Callout } from "@/components/Callout";

export default function CLIPage() {
  return (
    <div className="doc-content">
      <h1>CLI Reference</h1>
      <p className="text-lg text-neutral-600 dark:text-neutral-400">
        The <code>lfh</code> command is the primary interface for managing your
        lfhai cluster.
      </p>

      <h2>Global Options</h2>
      <CodeBlock
        code={`lfh [OPTIONS] COMMAND [ARGS]...

Options:
  -c, --controller TEXT  Controller URL (default: http://localhost:8001)
  -g, --gateway TEXT     Gateway URL (default: http://localhost:8000)
  --help                 Show help`}
        language="text"
      />

      <h2>Commands</h2>

      <h3>lfh status</h3>
      <p>Show cluster health and node status.</p>
      <TerminalBlock command="lfh status" label="Example" />
      <CodeBlock
        code={`Gateway:     ok
  Controller: connected
Controller:  ok

Nodes (2):
  a1b2c3d4e5f6  online  gpu-host [NVIDIA GeForce RTX 3060] models=['llama3.2']
  f6e5d4c3b2a1  online  cpu-host models=['whisper']`}
        language="text"
        filename="output"
      />

      <h3>lfh nodes</h3>
      <p>List all registered nodes with full details (JSON output).</p>
      <TerminalBlock command="lfh nodes" label="Example" />

      <h3>lfh models</h3>
      <p>List all available models across the cluster.</p>
      <TerminalBlock command="lfh models" label="Example" />
      <CodeBlock
        code={`  llama3.2
  whisper
  mistral`}
        language="text"
        filename="output"
      />

      <h3>lfh chat</h3>
      <p>Submit a chat request to the cluster.</p>
      <CodeBlock
        code={`lfh chat [OPTIONS] MODEL PROMPT

Arguments:
  MODEL    Model name (e.g., llama3.2)
  PROMPT   The user message

Options:
  --stream    Stream the response (default: false)`}
        language="text"
      />

      <p>Examples:</p>
      <TerminalBlock
        command='lfh chat llama3.2 "What is the capital of France?"'
        label="Non-streaming"
      />
      <TerminalBlock
        command='lfh chat --stream llama3.2 "Tell me a joke"'
        label="Streaming"
        variant="highlight"
      />

      <h3>lfh controller</h3>
      <p>Start the controller server.</p>
      <CodeBlock
        code={`lfh controller [OPTIONS]

Options:
  --host TEXT   Bind address (default: 0.0.0.0)
  --port INT    Port (default: 8001)`}
        language="text"
      />
      <TerminalBlock command="lfh controller" label="Start controller" />

      <h3>lfh gateway</h3>
      <p>Start the API gateway.</p>
      <CodeBlock
        code={`lfh gateway [OPTIONS]

Options:
  --host TEXT          Bind address (default: 0.0.0.0)
  --port INT           Port (default: 8000)
  --controller-url URL Controller URL`}
        language="text"
      />
      <TerminalBlock command="lfh gateway" label="Start gateway" />

      <h3>lfh worker start</h3>
      <p>Start a worker daemon on this machine.</p>
      <CodeBlock
        code={`lfh worker start [OPTIONS]

Options:
  -c, --controller-url URL  Controller URL (default: http://localhost:8001)
  -p, --port INT            Worker port (default: 8002)
  -o, --ollama-url URL      Ollama URL (default: http://localhost:11434)`}
        language="text"
      />

      <p>Examples:</p>
      <TerminalBlock
        command="lfh worker start"
        label="Default (localhost)"
      />
      <TerminalBlock
        command="lfh worker start -c http://192.168.1.100:8001 -p 8003"
        label="Custom controller and port"
        variant="highlight"
      />

      <Callout type="tip">
        Run <code>lfh worker start</code> on each machine that should
        participate in the cluster. The worker auto-detects GPU, models, and
        hardware capabilities.
      </Callout>

      <h3>lfh worker status</h3>
      <p>Check the status of the local worker.</p>
      <TerminalBlock command="lfh worker status" label="Example" />
      <CodeBlock
        code={`Node ID:  worker-gpu-host-8002
Status:   online
Ollama:   http://localhost:11434
Models:   llama3.2, mistral, whisper`}
        language="text"
        filename="output"
      />

      <h2>Common Workflows</h2>

      <h3>Start a 2-node cluster</h3>
      <CodeBlock
        code={`# Machine 1: Controller
lfh controller

# Machine 2: GPU Worker
lfh worker start -c http://machine1:8001

# Any machine: Test
lfh status
lfh chat llama3.2 "Hello!"`}
        language="bash"
      />

      <h3>Start all services on one machine</h3>
      <CodeBlock
        code={`# Terminal 1: Controller
lfh controller

# Terminal 2: Gateway
lfh gateway

# Terminal 3: Worker
lfh worker start -c http://localhost:8001`}
        language="bash"
      />
    </div>
  );
}
