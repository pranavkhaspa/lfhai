"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

interface NavGroup {
  title: string;
  items: { label: string; href: string; badge?: string }[];
}

const navigation: NavGroup[] = [
  {
    title: "Getting Started",
    items: [
      { label: "Introduction", href: "/docs" },
      { label: "Installation", href: "/docs/install" },
      { label: "Quickstart", href: "/docs/quickstart" },
    ],
  },
  {
    title: "Core Concepts",
    items: [
      { label: "Architecture", href: "/docs/architecture" },
      { label: "Configuration", href: "/docs/configuration" },
    ],
  },
  {
    title: "Reference",
    items: [
      { label: "CLI", href: "/docs/cli" },
      { label: "API", href: "/docs/api" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:block fixed top-16 bottom-0 w-[280px] border-r border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 overflow-y-auto">
      <nav className="p-6 space-y-8">
        {navigation.map((group) => (
          <div key={group.title}>
            <h4 className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-neutral-400 dark:text-neutral-500">
              {group.title}
            </h4>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={clsx(
                        "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-300"
                          : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-50 dark:hover:bg-neutral-900"
                      )}
                    >
                      {isActive && (
                        <div className="h-1.5 w-1.5 rounded-full bg-brand-600" />
                      )}
                      {item.label}
                      {item.badge && (
                        <span className="ml-auto rounded-full bg-brand-50 dark:bg-brand-950 px-2 py-0.5 text-[10px] font-medium text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-800">
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
