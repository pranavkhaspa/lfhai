import Link from "next/link";
import { Logo } from "./Logo";

const REPO = "https://github.com/pranavkhaspa/lfhai";

const sections: { title: string; links: { label: string; href: string; external?: boolean }[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Documentation", href: "/docs" },
      { label: "Quickstart", href: "/docs/quickstart" },
      { label: "Installation", href: "/docs/install" },
    ],
  },
  {
    title: "Reference",
    links: [
      { label: "Architecture", href: "/docs/architecture" },
      { label: "CLI", href: "/docs/cli" },
      { label: "API", href: "/docs/api" },
    ],
  },
  {
    title: "Community",
    links: [
      { label: "GitHub", href: REPO, external: true },
      { label: "Issues", href: `${REPO}/issues`, external: true },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-zinc-200/80 bg-zinc-50/50 dark:border-zinc-800/80 dark:bg-zinc-950/50">
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
          <div className="col-span-2">
            <Logo />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
              A local-first runtime that spreads AI inference across the
              hardware you already own. Private, open source, and self-hosted.
            </p>
          </div>
          {sections.map((section) => (
            <div key={section.title}>
              <p className="mb-3 text-[11px] font-medium uppercase tracking-widest text-zinc-500 dark:text-zinc-400">
                {section.title}
              </p>
              <ul className="space-y-2">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      target={link.external ? "_blank" : undefined}
                      rel={link.external ? "noopener noreferrer" : undefined}
                      className="text-sm text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-white"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col items-center justify-between gap-4 border-t border-zinc-200 pt-8 text-xs text-zinc-500 sm:flex-row dark:border-zinc-800 dark:text-zinc-400">
          <p>© 2026 lfhai — MIT License.</p>
          <p className="font-mono">local-first · heterogeneous · open source</p>
        </div>
      </div>
    </footer>
  );
}