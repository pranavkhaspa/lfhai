"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X, ExternalLink } from "lucide-react";
import clsx from "clsx";

const navItems = [
  { label: "Docs", href: "/docs" },
  { label: "GitHub", href: "https://github.com/your-org/lfhai", external: true },
];

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-neutral-200 dark:border-neutral-800 bg-white/80 dark:bg-neutral-950/80 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 shadow-lg shadow-brand-600/20 group-hover:shadow-brand-600/40 transition-shadow">
              <svg viewBox="0 0 32 32" fill="none" className="h-5 w-5">
                <path d="M8 16L14 10L20 16L14 22Z" fill="white" opacity="0.9" />
                <path d="M14 16L20 10L26 16L20 22Z" fill="white" opacity="0.6" />
              </svg>
            </div>
            <span className="text-xl font-bold tracking-tight text-neutral-900 dark:text-white">
              lfhai
            </span>
            <span className="hidden sm:inline-flex items-center rounded-full bg-brand-50 dark:bg-brand-950 px-2.5 py-0.5 text-xs font-medium text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-800">
              v0.1.0
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "px-3 py-2 text-sm font-medium rounded-lg transition-colors",
                  pathname?.startsWith(item.href)
                    ? "text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-950"
                    : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800"
                )}
                target={item.external ? "_blank" : undefined}
                rel={item.external ? "noopener noreferrer" : undefined}
              >
                {item.label}
                {item.external && (
                  <ExternalLink className="ml-1 inline-block h-3 w-3" />
                )}
              </Link>
            ))}
            <div className="ml-4 pl-4 border-l border-neutral-200 dark:border-neutral-700">
              <Link
                href="/docs/quickstart"
                className="inline-flex items-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 hover:bg-brand-700 hover:shadow-brand-600/40 transition-all"
              >
                Get Started
              </Link>
            </div>
          </nav>

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 rounded-lg text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      {mobileOpen && (
        <div className="md:hidden border-t border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950">
          <div className="px-4 py-3 space-y-1">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="block px-3 py-2 text-sm font-medium rounded-lg text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                target={item.external ? "_blank" : undefined}
                onClick={() => setMobileOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <Link
              href="/docs/quickstart"
              className="block px-3 py-2 text-sm font-semibold text-brand-600"
              onClick={() => setMobileOpen(false)}
            >
              Get Started
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
