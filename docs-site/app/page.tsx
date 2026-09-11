import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { InstallCommand } from "@/components/InstallCommand";
import { CodeBlock } from "@/components/CodeBlock";

const REPO = "https://github.com/pranavkhaspa/lfhai";

const features = [
  {
    n: "01",
    title: "Any hardware",
    description:
      "GPUs, CPUs, and edge devices in one cluster. lfhai routes each request to the machine best suited for it.",
  },
  {
    n: "02",
    title: "One API",
    description:
      "OpenAI-compatible endpoints make lfhai a drop-in replacement. Swap your provider and nothing else changes.",
  },
  {
    n: "03",
    title: "Private by default",
    description:
      "Everything runs on your machines. Optional tailcat tunnels encrypt node-to-node traffic without accounts.",
  },
  {
    n: "04",
    title: "Self-healing",
    description:
      "Workers report health every three seconds. Failures are detected automatically and requests re-routed.",
  },
  {
    n: "05",
    title: "Ollama-powered",
    description:
      "Run any model Ollama supports — quantized weights served from local VRAM, tuned per-machine.",
  },
  {
    n: "06",
    title: "Open source",
    description:
      "MIT licensed. A single Python package you can read, audit, and extend. No telemetry, no lock-in.",
  },
];

const steps = [
  {
    title: "Start the controller",
    text: "Any machine coordinates the cluster. It routes requests and tracks node health — no GPU needed.",
    code: "lfh controller",
  },
  {
    title: "Add workers",
    text: "Run the worker on each machine with Ollama. Hardware and models are detected automatically.",
    code: "lfh worker start -c http://host:8001",
  },
  {
    title: "Send requests",
    text: "One endpoint for every model across every node. Stream or wait — the API speaks OpenAI.",
    code: `curl ${"http://host:8000"}/v1/chat/completions \\
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"hi"}]}'`,
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <Header />

      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Subtle radial wash */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-[560px] bg-[radial-gradient(60%_60%_at_50%_0%,#e0e7ff_0%,transparent_100%)] opacity-60 dark:bg-[radial-gradient(60%_60%_at_50%_0%,#312e81_0%,transparent_100%)] dark:opacity-40"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-[linear-gradient(to_bottom,transparent,#ffffff)] dark:bg-[linear-gradient(to_bottom,transparent,#09090b)]"
        />

        <div className="relative mx-auto max-w-7xl px-4 pb-24 pt-24 sm:px-6 lg:px-8 sm:pt-32">
          <div className="mx-auto max-w-3xl text-center">
            <p className="mb-6 font-mono text-xs uppercase tracking-[0.2em] text-zinc-400 dark:text-zinc-400">
              v1.0 · Local-first heterogeneous AI runtime
            </p>
            <h1 className="text-balance text-4xl font-semibold leading-[1.08] tracking-tight text-zinc-950 sm:text-5xl md:text-6xl dark:text-white">
              AI inference across every machine you own.
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-zinc-600 dark:text-zinc-300">
              lfhai spreads LLM workloads across your GPUs, CPUs, and edge
              devices through one OpenAI-compatible API. Local-first, private,
              and free to self-host.
            </p>

            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                href="/docs/quickstart"
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-zinc-700 sm:w-auto dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                Deploy a cluster
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs"
                className="inline-flex w-full items-center justify-center rounded-lg border border-zinc-300 bg-white px-5 py-2.5 text-sm font-medium text-zinc-800 transition-colors hover:bg-zinc-50 sm:w-auto dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                Read the docs
              </Link>
            </div>
          </div>

          {/* Install terminal */}
          <div className="mx-auto mt-16 max-w-2xl">
            <InstallCommand label="shell" />
            <p className="mt-3 text-center text-xs text-zinc-400 dark:text-zinc-400">
              Installs lfhai, Ollama, and a worker on any machine.
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-y border-zinc-200/80 bg-zinc-50/60 dark:border-zinc-800/80 dark:bg-zinc-900/30">
        <div className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
          <div className="mb-16 grid gap-8 md:grid-cols-2 md:items-end">
            <h2 className="max-w-md text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl dark:text-white">
              A cluster that behaves like one machine.
            </h2>
            <p className="max-w-md text-base leading-relaxed text-zinc-600 dark:text-zinc-300">
              lfhai gives you the properties of a data-center cluster — routing,
              failover, a unified API — without the data center, or the bill.
            </p>
          </div>

          <div className="grid gap-px overflow-hidden rounded-xl border border-zinc-200 bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-800 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => (
              <div
                key={f.n}
                className="group bg-white p-7 transition-colors hover:bg-zinc-50 dark:bg-zinc-950 dark:hover:bg-zinc-900"
              >
                <p className="font-mono text-xs text-zinc-300 transition-colors group-hover:text-brand-500 dark:text-zinc-600 dark:group-hover:text-brand-400">
                  {f.n}
                </p>
                <h3 className="mt-3 text-[15px] font-semibold text-zinc-900 dark:text-white">
                  {f.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
                  {f.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
        <div className="grid gap-16 lg:grid-cols-2 lg:gap-24">
          <div>
            <p className="mb-3 font-mono text-xs uppercase tracking-[0.2em] text-zinc-400 dark:text-zinc-400">
              Quickstart
            </p>
            <h2 className="text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl dark:text-white">
              Three commands to a cluster.
            </h2>
            <div className="mt-10 space-y-10">
              {steps.map((step, i) => (
                <div key={step.title} className="flex gap-5">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-zinc-300 font-mono text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
                    {i + 1}
                  </span>
                  <div>
                    <h3 className="text-[15px] font-semibold text-zinc-900 dark:text-white">
                      {step.title}
                    </h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
                      {step.text}
                    </p>
                    <CodeBlock code={step.code} filename="terminal" copyButton={false} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:pt-24">
            <p className="mb-3 font-mono text-xs uppercase tracking-[0.2em] text-zinc-400 dark:text-zinc-400">
              Architecture
            </p>
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-white">
              Gateway → Controller → Workers
            </h3>
            <div className="mt-6 overflow-hidden rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
              <div className="border-b border-zinc-200 bg-zinc-50 px-4 py-2.5 dark:border-zinc-800 dark:bg-zinc-950/60">
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-zinc-300 dark:bg-zinc-700" />
                  <span className="h-2.5 w-2.5 rounded-full bg-zinc-300 dark:bg-zinc-700" />
                  <span className="h-2.5 w-2.5 rounded-full bg-zinc-300 dark:bg-zinc-700" />
                </div>
              </div>
              <div className="p-5">
                <div className="font-mono text-[13px] leading-8">
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-400">client</span>
                    <span className="text-zinc-300">→</span>
                    <Node name="Gateway · :8000" />
                  </div>
                  <div className="flex items-center gap-2 pl-8">
                    <span className="text-zinc-400">→</span>
                    <Node name="Controller · :8001" tone="brand" />
                  </div>
                  <div className="pl-16 font-mono text-[11px] text-zinc-400">
                    ├─ registry · routing · health
                  </div>
                  <div className="flex items-center gap-2 pl-8">
                    <span className="text-zinc-400">→</span>
                    <Node name="Worker · :8002" tone="outline" />
                    <span className="text-zinc-400">→</span>
                    <span className="rounded-md border border-zinc-200 px-2 py-0.5 text-zinc-400 dark:border-zinc-700">
                      Ollama
                    </span>
                  </div>
                  <div className="flex items-center gap-2 pl-8">
                    <span className="text-zinc-400">→</span>
                    <Node name="Worker · :8002" tone="outline" />
                    <span className="text-zinc-400">→</span>
                    <span className="rounded-md border border-zinc-200 px-2 py-0.5 text-zinc-400 dark:border-zinc-700">
                      Ollama
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-zinc-400 dark:text-zinc-400">
              Every node registers, reports capability, and runs whichever model
              it can. The controller never touches model weights.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-zinc-200/80 bg-zinc-50/60 dark:border-zinc-800/80 dark:bg-zinc-900/30">
        <div className="mx-auto max-w-3xl px-4 py-24 text-center sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl dark:text-white">
            Cluster the machines you already own.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-zinc-600 dark:text-zinc-300">
            Started with an old server and a gaming PC. Ends with a private
            inference cluster that answers, streams, and heals itself.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/docs/quickstart"
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-zinc-700 sm:w-auto dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              Get started
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href={REPO}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-full items-center justify-center rounded-lg border border-zinc-300 bg-white px-5 py-2.5 text-sm font-medium text-zinc-800 transition-colors hover:bg-zinc-50 sm:w-auto dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              Star on GitHub
            </a>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}

function Node({
  name,
  tone = "default",
}: {
  name: string;
  tone?: "default" | "brand" | "outline";
}) {
  const tones = {
    default: "border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-200",
    brand:
      "border-brand-200 bg-brand-50 text-brand-700 dark:border-brand-900/60 dark:bg-brand-950/50 dark:text-brand-300",
    outline:
      "border-zinc-200 text-zinc-600 dark:border-zinc-700 dark:text-zinc-300",
  } as const;

  return (
    <span
      className={`rounded-md border px-2 py-0.5 ${tones[tone]}`}
    >
      {name}
    </span>
  );
}