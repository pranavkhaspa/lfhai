"use client";

import type { ReactNode } from "react";
import { Info, AlertTriangle, CheckCircle2 } from "lucide-react";
import clsx from "clsx";

interface CalloutProps {
  type?: "info" | "warning" | "success";
  title?: string;
  children: ReactNode;
}

const icons = {
  info: Info,
  warning: AlertTriangle,
  success: CheckCircle2,
};

const accent = {
  info: "text-brand-500",
  warning: "text-amber-500",
  success: "text-emerald-500",
};

export function Callout({ type = "info", title, children }: CalloutProps) {
  const Icon = icons[type];

  return (
    <div className="my-6 flex gap-3.5 rounded-xl border border-zinc-200 bg-zinc-50/70 px-4 py-3.5 dark:border-zinc-800 dark:bg-zinc-900/60">
      <Icon className={clsx("mt-0.5 h-4 w-4 shrink-0", accent[type])} />
      <div className="min-w-0 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
        {title && (
          <p className="mb-1 text-sm font-semibold text-zinc-900 dark:text-white">
            {title}
          </p>
        )}
        <div className="[&>p:last-child]:mb-0">{children}</div>
      </div>
    </div>
  );
}