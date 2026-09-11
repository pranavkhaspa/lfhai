import { CodeBlock } from "@/components/CodeBlock";
import { Callout } from "@/components/Callout";

export default function ConfigurationPage() {
  return (
    <div className="doc-content">
      <h1>Configuration</h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-300">
        Configure lfhai components via CLI flags and environment variables.
      </p>

      <h2>Controller</h2>
      <table>
        <thead>
          <tr>
            <th>Flag</th>
            <th>Default</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>--host</code></td>
            <td>0.0.0.0</td>
            <td>Bind address</td>
          </tr>
          <tr>
            <td><code>--port</code></td>
            <td>8001</td>
            <td>Listen port</td>
          </tr>
        </tbody>
      </table>

      <CodeBlock
        code={`# Start on a specific port
lfh controller --port 9001

# Bind to localhost only
lfh controller --host 127.0.0.1`}
        language="bash"
      />

      <h2>Worker</h2>
      <table>
        <thead>
          <tr>
            <th>Flag</th>
            <th>Default</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>-c, --controller-url</code></td>
            <td>http://localhost:8001</td>
            <td>Controller URL to register with</td>
          </tr>
          <tr>
            <td><code>-p, --port</code></td>
            <td>8002</td>
            <td>Worker HTTP port</td>
          </tr>
          <tr>
            <td><code>-o, --ollama-url</code></td>
            <td>http://localhost:11434</td>
            <td>Ollama API URL</td>
          </tr>
        </tbody>
      </table>

      <CodeBlock
        code={`# Connect to a remote controller
lfh worker start -c http://192.168.1.100:8001

# Custom Ollama URL
lfh worker start -o http://gpu-server:11434

# All options
lfh worker start -c http://ctrl:8001 -p 8003 -o http://ollama:11434`}
        language="bash"
      />

      <h2>Gateway</h2>
      <table>
        <thead>
          <tr>
            <th>Flag</th>
            <th>Default</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>--host</code></td>
            <td>0.0.0.0</td>
            <td>Bind address</td>
          </tr>
          <tr>
            <td><code>--port</code></td>
            <td>8000</td>
            <td>Listen port</td>
          </tr>
          <tr>
            <td><code>--controller-url</code></td>
            <td>http://localhost:8001</td>
            <td>Controller URL</td>
          </tr>
        </tbody>
      </table>

      <h2>Systemd Configuration</h2>
      <p>
        When using the install script, the systemd service is created at{" "}
        <code>/etc/systemd/system/lfhai-worker.service</code>. Edit it to
        customize:
      </p>

      <CodeBlock
        code={`[Unit]
Description=lfhai Worker Daemon
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/lfhai
ExecStart=/path/to/lfhai/.venv/bin/python -m lfhai.cli worker start \\
    -c http://controller-ip:8001 \\
    -p 8002 \\
    -o http://localhost:11434
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target`}
        language="ini"
        filename="lfhai-worker.service"
      />

      <CodeBlock
        code={`# Reload after changes
sudo systemctl daemon-reload

# Restart the service
sudo systemctl restart lfhai-worker`}
        language="bash"
      />

      <h2>Port Reference</h2>
      <table>
        <thead>
          <tr>
            <th>Service</th>
            <th>Default Port</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Gateway</td>
            <td>8000</td>
            <td>User-facing API</td>
          </tr>
          <tr>
            <td>Controller</td>
            <td>8001</td>
            <td>Cluster coordination</td>
          </tr>
          <tr>
            <td>Worker</td>
            <td>8002</td>
            <td>Task execution</td>
          </tr>
          <tr>
            <td>Ollama</td>
            <td>11434</td>
            <td>Model inference</td>
          </tr>
        </tbody>
      </table>

      <Callout type="warning">
        All ports can be changed via CLI flags. Make sure firewall rules allow
        traffic on the configured ports between cluster machines.
      </Callout>

      <h2>Network Configuration</h2>

      <h3>Same LAN</h3>
      <p>
        For machines on the same LAN, no special network configuration is
        needed. Workers connect to the controller via its IP address.
      </p>

      <h3>Different Networks</h3>
      <p>
        For machines on different networks, use{" "}
        <a href="https://github.com/tailscale/tailcat">tailcat</a> to create
        encrypted tunnels:
      </p>

      <CodeBlock
        code={`# On the controller machine:
tailcat serve 8001
# Note the tc... address

# On the worker machine:
tailcat forward <tc-address> 8001:8001
# Worker can now reach controller at localhost:8001`}
        language="bash"
      />

      <h3>Firewall Rules</h3>
      <p>If using a firewall, allow these ports:</p>
      <CodeBlock
        code={`# ufw (Ubuntu)
sudo ufw allow 8000/tcp  # Gateway
sudo ufw allow 8001/tcp  # Controller
sudo ufw allow 8002/tcp  # Worker

# iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8001 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8002 -j ACCEPT`}
        language="bash"
      />
    </div>
  );
}
