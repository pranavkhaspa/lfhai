import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function DocsIndex() {
  return (
    <div className="doc-content">
      <h1>lfhai Documentation</h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-300">
        Welcome to lfhai &mdash; the local-first heterogeneous AI runtime.
        Coordinate mismatched consumer hardware into a unified AI inference
        system.
      </p>

      <h2>What is lfhai?</h2>
      <p>
        lfhai is a distributed compute fabric that lets you pool GPUs, CPUs, and
        edge devices into a single AI cluster. Instead of buying expensive
        uniform GPU servers, lfhai routes inference tasks to whichever machine
        in your network has the right hardware.
      </p>

      <h2>Key Concepts</h2>
      <ul>
        <li>
          <strong>Controller</strong> &mdash; The central coordinator that
          tracks nodes, routes tasks, and monitors health via heartbeats.
        </li>
        <li>
          <strong>Worker</strong> &mdash; A daemon running on each machine that
          interfaces with Ollama to execute inference tasks.
        </li>
        <li>
          <strong>Gateway</strong> &mdash; An OpenAI-compatible HTTP API that
          accepts chat completions requests and forwards them to the controller.
        </li>
        <li>
          <strong>Router</strong> &mdash; Decides which node handles each task
          based on model availability, GPU presence, and load.
        </li>
      </ul>

      <h2>Quick Links</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6">
        {[
          {
            title: "Installation",
            href: "/docs/install",
            description: "Install lfhai on your machine",
          },
          {
            title: "Quickstart",
            href: "/docs/quickstart",
            description: "Get your first cluster running",
          },
          {
            title: "Architecture",
            href: "/docs/architecture",
            description: "How lfhai works under the hood",
          },
          {
            title: "CLI Reference",
            href: "/docs/cli",
            description: "All lfh commands",
          },
          {
            title: "API Reference",
            href: "/docs/api",
            description: "HTTP endpoints",
          },
          {
            title: "Configuration",
            href: "/docs/configuration",
            description: "Options and environment variables",
          },
        ].map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="group flex flex-col rounded-xl border border-zinc-200 dark:border-zinc-800 p-5 transition-colors hover:border-brand-300 dark:hover:border-brand-700"
          >
            <h3 className="text-base font-semibold text-zinc-900 group-hover:text-zinc-900 dark:text-white dark:group-hover:text-white transition-colors">
              {item.title}
              <ArrowRight className="inline-block ml-1.5 h-4 w-4 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
            </h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">
              {item.description}
            </p>
          </Link>
        ))}
      </div>

      <h2>System Requirements</h2>
      <ul>
        <li>Python 3.10 or later</li>
        <li>Ollama installed and running (on worker nodes)</li>
        <li>2+ CPU cores, 4GB RAM minimum</li>
        <li>NVIDIA GPU recommended for LLM inference</li>
      </ul>
    </div>
  );
}
