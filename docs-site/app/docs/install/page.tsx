import { CodeBlock, InlineCode } from "@/components/CodeBlock";
import { TerminalBlock } from "@/components/TerminalBlock";
import { InstallCommand } from "@/components/InstallCommand";
import { Callout } from "@/components/Callout";

export default function InstallPage() {
  return (
    <div className="doc-content">
      <h1>Installation</h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-300">
        Install lfhai on any machine running Linux or macOS.
      </p>

      <h2>Quick Install</h2>
      <p>
        The fastest way to install lfhai and its dependencies (including
        Ollama):
      </p>
      <InstallCommand label="One-line install" />

      <p>This script will:</p>
      <ul>
        <li>Check for Python 3.10+ (install if missing)</li>
        <li>Install Ollama (if not present)</li>
        <li>Pull a default model if no models exist</li>
        <li>Install lfhai into <code>~/.lfhai/venv</code></li>
        <li>Place <code>lfh</code> on your PATH (via <code>~/.local/bin</code>)</li>
        <li>Join the cluster (if a <code>--join-token</code> is provided)</li>
        <li>Create and start a systemd service (Linux only)</li>
      </ul>

      <p>
        On each worker machine you can install <em>and</em> join the cluster in
        a single command. Mint a token on the controller, then run:
      </p>
      <TerminalBlock
        command={`curl -fsSL <site-url>/install.sh | bash -s -- --join-token <token>`}
        label="Install + join in one command"
      />

      <h2>Join the Cluster</h2>
      <p>
        A machine&apos;s <em>first</em> step on the cluster is to be admitted
        with a one-time join token. No IP addresses to find, no ports to
        configure &mdash; the token carries everything.
      </p>
      <p>
        On the controller machine, mint a token (steps below), then run
        <code>lfh node join</code> on each worker:
      </p>
      <TerminalBlock
        command="lfh token create"
        label="Controller machine"
      />
      <TerminalBlock
        command="lfh node join <token>"
        label="Each worker machine"
      />

      <p>
        Tokens expire after one hour, are single-use, and are stored
        hash-only on the controller. The worker saves its credential to{" "}
        <code>~/.lfhai/credentials.json</code> (mode 0600) and uses it for all
        future registrations and heartbeats.
      </p>

      <Callout type="info">
        List or revoke tokens from the controller machine with{" "}
        <code>lfh token list</code> and <code>lfh token revoke</code>.
      </Callout>

      <h2>Install from Source</h2>
      <p>
        Clone the repository and install in development mode:
      </p>
      <CodeBlock
        code={`git clone https://github.com/pranavkhaspa/lfhai.git
cd lfhai
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"`}
        language="bash"
      />

      <h2>Install the Package</h2>
      <p>
        The one-line installer pulls the packaged wheel from this site
        (<code>/lfhai-0.1.5-py3-none-any.whl</code>) so no repo access or
        credentials are needed. To install the package directly into the
        current Python environment:
      </p>
      <TerminalBlock
        command={`pip install https://lfhai.vercel.app/lfhai-0.1.5-py3-none-any.whl`}
        label="pip"
      />

      <h2>Install Ollama</h2>
      <p>
        lfhai requires <a href="https://ollama.com" target="_blank" rel="noopener noreferrer">Ollama</a> on each worker node. Ollama handles model loading and inference.
      </p>
      <TerminalBlock
        command="curl -fsSL https://ollama.com/install.sh | sh"
        label="Install Ollama"
      />

      <p>
        After installing Ollama, pull a model:
      </p>
      <TerminalBlock
        command="ollama pull llama3.2"
        label="Pull a model"
      />

      <h2>Windows (native)</h2>
      <p>
        The installer script is POSIX-only (bash + systemd), but lfhai itself
        is pure Python and runs natively on Windows. Do not use WSL unless you
        want the full one-click experience — WSL2 gives you the complete{" "}
        <code>install.sh</code> path. For native Windows:
      </p>
      <ol>
        <li>
          Install Python 3.10+ and the Windows{" "}
          <a href="https://ollama.com/download/windows" target="_blank" rel="noopener noreferrer">Ollama</a>{" "}
          app (defaults to <code>http://localhost:11434</code>).
        </li>
        <li>
          <code>pip install https://lfhai.vercel.app/lfhai-0.1.5-py3-none-any.whl</code>
        </li>
        <li>
          Join the cluster and start the worker:
          <TerminalBlock
            command="lfh node join &lt;token&gt;&#10;lfh worker start"
            label="PowerShell"
          />
        </li>
        <li>
          Open TCP 8000/8001/8002 in Windows Firewall so other nodes can reach
          this machine.
        </li>
      </ol>
      <p>
        Android nodes (roadmap) run the same Python worker under Termux with
        proot-distro once Ollama is bundled there.
      </p>

      <h2>Install tailcat (Optional)</h2>
      <p>
        For encrypted tunnels between nodes on different networks, install{" "}
        <a href="https://github.com/tailscale/tailcat" target="_blank" rel="noopener noreferrer">tailcat</a>:
      </p>

      <h3>macOS</h3>
      <TerminalBlock command="brew install tailcat" label="Homebrew" />

      <h3>Go</h3>
      <TerminalBlock
        command="go install github.com/tailscale/tailcat/cmd/tailcat@latest"
        label="Go install"
      />

      <h3>Pre-built binaries</h3>
      <p>
        Download from the{" "}
        <a href="https://github.com/tailscale/tailcat/releases" target="_blank" rel="noopener noreferrer">
          GitHub Releases page
        </a>
        .
      </p>

      <h2>Verify Installation</h2>
      <CodeBlock
        code={`# Check lfhai is installed
lfh --help

# Check controller starts
lfh controller &
lfh status

# Check worker status
lfh worker status`}
        language="bash"
      />

      <h2>Systemd Service (Linux)</h2>
      <p>
        The install script creates a systemd service for the worker daemon:
      </p>
      <CodeBlock
        code={`# Start the worker service
sudo systemctl start lfhai-worker

# Enable on boot
sudo systemctl enable lfhai-worker

# Check status
sudo systemctl status lfhai-worker

# View logs
sudo journalctl -u lfhai-worker -f`}
        language="bash"
      />

      <Callout type="info">
        The worker service connects to the controller at localhost:8001 by
        default. Edit <code>/etc/systemd/system/lfhai-worker.service</code> to
        change the controller URL.
      </Callout>
    </div>
  );
}
