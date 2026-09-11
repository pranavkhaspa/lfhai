"use client";

import { useState, type ReactNode } from "react";
import { Copy, Check } from "lucide-react";
import clsx from "clsx";

export type TerminalVariant = "default" | "accent";

interface TerminalBlockProps {
  command: string;
  label?: string;
  variant?: TerminalVariant;
  children?: ReactNode;
}

export function TerminalBlock({
  command,
  label,
  variant = "default",
  children,
}: TerminalBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-6 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      {/* Window chrome */}
      <div className="flex items-center gap-3 border-b border-zinc-200 bg-zinc-50 px-4 py-2.5 dark:border-zinc-800 dark:bg-zinc-950/60">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-zinc-300 dark:bg-zinc-700" />
          <span className="h-2.5 w-2.5 rounded-full bg-zinc-300 dark:bg-zinc-700" />
          <span className="h-2.5 w-2.5 rounded-full bg-zinc-300 dark:bg-zinc-700" />
        </div>
        {label && (
          <span className="flex-1 truncate text-center font-mono text-[11px] text-zinc-500 dark:text-zinc-400">
            {label}
          </span>
        )}
        <button
          onClick={handleCopy}
          aria-label="Copy command"
          className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-emerald-500" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      </div>

      {/* Command body */}
      <div className="px-4 py-3.5">
        <div className="flex items-start gap-2.5">
          <span
            className={clsx(
              "mt-px select-none font-mono text-sm",
              variant === "accent"
                ? "text-brand-500 dark:text-brand-400"
                : "text-zinc-400"
            )}
          >
            $
          </span>
          <code className="break-all font-mono text-[13px] leading-relaxed text-zinc-800 dark:text-zinc-200">
            {command}
          </code>
        </div>
        {children}
      </div>
    </div>
  );
}