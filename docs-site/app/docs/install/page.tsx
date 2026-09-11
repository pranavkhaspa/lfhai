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
        <li>Install lfhai Python package</li>
        <li>Create a systemd service (Linux only)</li>
      </ul>

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

      <h2>Install via pip</h2>
      <p>
        Install from PyPI (coming soon):
      </p>
      <TerminalBlock
        command="pip install lfhai"
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
