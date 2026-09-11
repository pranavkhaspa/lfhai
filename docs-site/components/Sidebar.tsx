"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

interface NavItem {
  label: string;
  href: string;
  badge?: string;
}

const navigation: { title: string; items: NavItem[] }[] = [
  {
    title: "Getting started",
    items: [
      { label: "Introduction", href: "/docs" },
      { label: "Installation", href: "/docs/install" },
      { label: "Quickstart", href: "/docs/quickstart" },
    ],
  },
  {
    title: "Core concepts",
    items: [
      { label: "Architecture", href: "/docs/architecture" },
      { label: "Configuration", href: "/docs/configuration" },
    ],
  },
  {
    title: "Reference",
    items: [
      { label: "CLI", href: "/docs/cli" },
      { label: "API", href: "/docs/api", badge: "v1" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed bottom-0 left-0 top-16 hidden w-64 overflow-y-auto border-r border-zinc-200/80 bg-white px-4 py-8 lg:block dark:border-zinc-800/80 dark:bg-zinc-950">
      <nav className="space-y-8">
        {navigation.map((group) => (
          <div key={group.title}>
            <p className="mb-2 px-3 text-[11px] font-medium uppercase tracking-widest text-zinc-500 dark:text-zinc-400">
              {group.title}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={clsx(
                        "relative flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                        isActive
                          ? "text-zinc-900 dark:text-white"
                          : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-white"
                      )}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-brand-500" />
                      )}
                      {item.label}
                      {item.badge && (
                        <span className="ml-auto rounded-full border border-zinc-200 px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}