import Link from "next/link";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { TerminalBlock } from "@/components/TerminalBlock";
import {
  ArrowRight,
  Cpu,
  Globe,
  Shield,
  Zap,
  Server,
  Layers,
} from "lucide-react";

const features = [
  {
    icon: Cpu,
    title: "Heterogeneous Hardware",
    description:
      "Mix and match GPUs, CPUs, and edge devices. lfhai routes tasks to whichever node has the right hardware.",
  },
  {
    icon: Globe,
    title: "Local-First Networking",
    description:
      "Encrypted tunnels via tailcat. No cloud dependencies, no accounts required. Your data stays on your machines.",
  },
  {
    icon: Shield,
    title: "OpenAI-Compatible API",
    description:
      "Drop-in replacement for OpenAI endpoints. Use any client library that speaks the chat completions protocol.",
  },
  {
    icon: Zap,
    title: "Capability-Aware Routing",
    description:
      "The scheduler knows which node has which model, GPU, and VRAM. Tasks go to the optimal machine automatically.",
  },
  {
    icon: Server,
    title: "Heartbeat Monitoring",
    description:
      "Nodes self-report health every 3 seconds. Dead nodes are detected and removed from routing automatically.",
  },
  {
    icon: Layers,
    title: "Ollama Integration",
    description:
      "Wraps Ollama's inference engine. Run any model Ollama supports, distributed across your cluster.",
  },
];

const steps = [
  {
    step: "1",
    title: "Start the controller",
    description: "On any machine in your network",
    code: "lfh controller",
  },
  {
    step: "2",
    title: "Start a worker",
    description: "On each GPU/CPU machine with Ollama",
    code: "lfh worker start -c http://controller:8001",
  },
  {
    step: "3",
    title: "Send requests",
    description: "Route through the unified API",
    code: 'curl -X POST http://controller:8000/v1/chat/completions \\\n  -H "Content-Type: application/json" \\\n  -d \'{"model":"llama3","messages":[{"role":"user","content":"Hello!"}]}\'',
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-brand-50/50 via-white to-white dark:from-brand-950/30 dark:via-neutral-950 dark:to-neutral-950" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-brand-400/10 dark:bg-brand-600/5 rounded-full blur-3xl" />

        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-20 pb-24 sm:pt-28 sm:pb-32">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 rounded-full border border-brand-200 dark:border-brand-800 bg-brand-50 dark:bg-brand-950 px-4 py-1.5 mb-8">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500" />
              </span>
              <span className="text-sm font-medium text-brand-700 dark:text-brand-300">
                V1 Released &mdash; Now with working inference routing
              </span>
            </div>

            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-neutral-900 dark:text-white">
              One API.{" "}
              <span className="bg-gradient-to-r from-brand-600 to-brand-400 bg-clip-text text-transparent">
                Every machine.
              </span>
            </h1>
            <p className="mt-6 text-xl text-neutral-600 dark:text-neutral-400 max-w-2xl mx-auto leading-relaxed">
              lfhai coordinates mismatched consumer hardware into a unified AI
              inference system. GPUs, CPUs, old laptops &mdash; they all become
              one cluster.
            </p>

            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/docs/quickstart"
                className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-6 py-3.5 text-sm font-semibold text-white shadow-xl shadow-brand-600/25 hover:bg-brand-700 hover:shadow-brand-600/40 transition-all"
              >
                Get Started
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs/install"
                className="inline-flex items-center gap-2 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-6 py-3.5 text-sm font-semibold text-neutral-900 dark:text-white hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
              >
                Install
              </Link>
            </div>

            {/* Quick install */}
            <div className="mt-10 max-w-xl mx-auto">
              <TerminalBlock
                command="curl -fsSL https://lfhai.dev/install.sh | bash"
                label="Quick Install"
                variant="install"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 bg-neutral-50 dark:bg-neutral-900/50 border-y border-neutral-200 dark:border-neutral-800">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900 dark:text-white">
              Why lfhai?
            </h2>
            <p className="mt-4 text-lg text-neutral-600 dark:text-neutral-400 max-w-2xl mx-auto">
              Stop buying expensive GPU clusters. Use what you already have.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="group rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 p-6 hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-lg hover:shadow-brand-600/5 transition-all"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-950 text-brand-600 dark:text-brand-400 mb-4 group-hover:bg-brand-100 dark:group-hover:bg-brand-900 transition-colors">
                  <feature.icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-2">
                  {feature.title}
                </h3>
                <p className="text-sm text-neutral-600 dark:text-neutral-400 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900 dark:text-white">
              Three steps to your first cluster
            </h2>
            <p className="mt-4 text-lg text-neutral-600 dark:text-neutral-400">
              From zero to distributed inference in under a minute.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {steps.map((step) => (
              <div key={step.step} className="relative">
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-white font-bold text-sm">
                    {step.step}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">
                      {step.title}
                    </h3>
                    <p className="text-sm text-neutral-500 dark:text-neutral-400">
                      {step.description}
                    </p>
                  </div>
                </div>
                <TerminalBlock command={step.code} variant="highlight" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Architecture diagram */}
      <section className="py-24 bg-neutral-50 dark:bg-neutral-900/50 border-y border-neutral-200 dark:border-neutral-800">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900 dark:text-white mb-4">
            How it works
          </h2>
          <p className="text-lg text-neutral-600 dark:text-neutral-400 mb-12">
            Requests flow through the gateway to the controller, which routes
            them to the optimal worker node.
          </p>

          <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 p-8 shadow-xl">
            <div className="font-mono text-sm text-left text-neutral-700 dark:text-neutral-300 space-y-2">
              <div className="flex items-center gap-3">
                <span className="text-neutral-400">User</span>
                <span className="text-neutral-300">&rarr;</span>
                <span className="rounded-lg bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300 px-3 py-1 font-medium">
                  Gateway :8000
                </span>
                <span className="text-neutral-300">&rarr;</span>
                <span className="rounded-lg bg-brand-100 dark:bg-brand-900 text-brand-700 dark:text-brand-300 px-3 py-1 font-medium">
                  Controller :8001
                </span>
              </div>
              <div className="pl-32 text-neutral-400">|</div>
              <div className="pl-32 text-neutral-400">&darr; SQLite + Router</div>
              <div className="pl-32 text-neutral-400">|</div>
              <div className="flex items-center gap-3 pl-32">
                <span className="text-neutral-300">&rarr;</span>
                <span className="rounded-lg bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-300 px-3 py-1 font-medium">
                  Worker (GPU) :8002
                </span>
                <span className="text-neutral-400">&rarr;</span>
                <span className="rounded-lg bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 px-3 py-1">
                  Ollama :11434
                </span>
              </div>
              <div className="flex items-center gap-3 pl-32">
                <span className="text-neutral-300">&rarr;</span>
                <span className="rounded-lg bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-300 px-3 py-1 font-medium">
                  Worker (CPU) :8002
                </span>
                <span className="text-neutral-400">&rarr;</span>
                <span className="rounded-lg bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 px-3 py-1">
                  Ollama :11434
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900 dark:text-white mb-4">
            Ready to cluster your hardware?
          </h2>
          <p className="text-lg text-neutral-600 dark:text-neutral-400 mb-10">
            Install lfhai and turn your scattered machines into a unified AI
            inference system.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <TerminalBlock
              command="pip install lfhai"
              label="Install"
              variant="install"
            />
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
