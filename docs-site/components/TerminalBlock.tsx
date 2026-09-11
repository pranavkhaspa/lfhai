"use client";

import { useState } from "react";
import { Copy, Check, Terminal } from "lucide-react";

interface TerminalBlockProps {
  command: string;
  label?: string;
  variant?: "default" | "install" | "highlight";
}

export function TerminalBlock({
  command,
  label,
  variant = "default",
}: TerminalBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`group relative rounded-xl border overflow-hidden my-6 ${
        variant === "install"
          ? "border-brand-300 dark:border-brand-700 bg-gradient-to-br from-brand-50 to-white dark:from-brand-950 dark:to-neutral-900"
          : variant === "highlight"
            ? "border-emerald-300 dark:border-emerald-700 bg-gradient-to-br from-emerald-50 to-white dark:from-emerald-950 dark:to-neutral-900"
            : "border-neutral-200 dark:border-neutral-800 bg-neutral-950"
      }`}
    >
      {(label || true) && (
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-neutral-200 dark:border-neutral-800 bg-white/50 dark:bg-neutral-900/50">
          <div className="flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5 text-neutral-400" />
            <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
              {label || "Terminal"}
            </span>
          </div>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                Copy
              </>
            )}
          </button>
        </div>
      )}
      <div className="px-4 py-3 flex items-center gap-3">
        <span className="text-brand-500 dark:text-brand-400 font-mono text-sm select-none">$</span>
        <code className="font-mono text-sm text-neutral-800 dark:text-neutral-200 break-all">
          {command}
        </code>
      </div>
    </div>
  );
}
