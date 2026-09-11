"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import clsx from "clsx";
import { Logo } from "./Logo";

const REPO = "https://github.com/pranavkhaspa/lfhai";

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  const linkClass = (href: string) =>
    clsx(
      "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
      pathname?.startsWith(href)
        ? "text-zinc-900 dark:text-white"
        : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-white"
    );

  return (
    <header className="sticky top-0 z-50 border-b border-zinc-200/80 bg-white/85 backdrop-blur-xl dark:border-zinc-800/80 dark:bg-zinc-950/80">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Logo />

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex">
          <Link href="/docs" className={linkClass("/docs")}>
            Docs
          </Link>
          <a
            href={REPO}
            target="_blank"
            rel="noopener noreferrer"
            className={linkClass(REPO)}
          >
            GitHub
          </a>
          <Link
            href="/docs/quickstart"
            className="ml-3 rounded-lg bg-zinc-900 px-3.5 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors"
          >
            Get started
          </Link>
        </nav>

        {/* Mobile button */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
          className="rounded-md p-2 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 md:hidden"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile nav */}
      {mobileOpen && (
        <div className="border-t border-zinc-200 bg-white px-4 py-3 md:hidden dark:border-zinc-800 dark:bg-zinc-950">
          <nav className="flex flex-col gap-1">
            <Link
              href="/docs"
              onClick={() => setMobileOpen(false)}
              className="rounded-md px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Docs
            </Link>
            <a
              href={REPO}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              GitHub
            </a>
            <Link
              href="/docs/quickstart"
              onClick={() => setMobileOpen(false)}
              className="mt-1 rounded-md bg-zinc-900 px-3 py-2 text-center text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
            >
              Get started
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}