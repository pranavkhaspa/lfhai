"use client";

import React from "react";
import { AlertTriangle, Info, CheckCircle2, Lightbulb } from "lucide-react";
import clsx from "clsx";

interface CalloutProps {
  type?: "info" | "warning" | "success" | "tip";
  children: React.ReactNode;
}

const icons = {
  info: Info,
  warning: AlertTriangle,
  success: CheckCircle2,
  tip: Lightbulb,
};

const styles = {
  info: {
    bg: "bg-blue-50 dark:bg-blue-950/50",
    border: "border-blue-200 dark:border-blue-800",
    icon: "text-blue-600 dark:text-blue-400",
    title: "text-blue-900 dark:text-blue-200",
  },
  warning: {
    bg: "bg-amber-50 dark:bg-amber-950/50",
    border: "border-amber-200 dark:border-amber-800",
    icon: "text-amber-600 dark:text-amber-400",
    title: "text-amber-900 dark:text-amber-200",
  },
  success: {
    bg: "bg-emerald-50 dark:bg-emerald-950/50",
    border: "border-emerald-200 dark:border-emerald-800",
    icon: "text-emerald-600 dark:text-emerald-400",
    title: "text-emerald-900 dark:text-emerald-200",
  },
  tip: {
    bg: "bg-violet-50 dark:bg-violet-950/50",
    border: "border-violet-200 dark:border-violet-800",
    icon: "text-violet-600 dark:text-violet-400",
    title: "text-violet-900 dark:text-violet-200",
  },
};

export function Callout({ type = "info", children }: CalloutProps) {
  const Icon = icons[type];
  const style = styles[type];

  return (
    <div
      className={clsx(
        "rounded-xl border p-4 my-6",
        style.bg,
        style.border
      )}
    >
      <div className="flex gap-3">
        <Icon className={clsx("h-5 w-5 mt-0.5 shrink-0", style.icon)} />
        <div className="doc-content text-sm leading-relaxed min-w-0">
          {children}
        </div>
      </div>
    </div>
  );
}
