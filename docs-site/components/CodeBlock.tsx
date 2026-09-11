"use client";

import { useState, type ReactNode } from "react";
import { Copy, Check } from "lucide-react";

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  showLineNumbers?: boolean;
  copyButton?: boolean;
}

export function CodeBlock({
  code,
  filename,
  showLineNumbers = false,
  copyButton = true,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = code.split("\n");

  return (
    <div className="my-6 overflow-hidden rounded-xl border border-zinc-200 bg-zinc-900 dark:border-zinc-800">
      {/* Window chrome */}
      <div className="flex items-center gap-3 border-b border-zinc-800 bg-zinc-950/60 px-4 py-2.5">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
          <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
          <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
        </div>
        {filename && (
          <span className="flex-1 truncate text-center font-mono text-[11px] text-zinc-500">
            {filename}
          </span>
        )}
        {copyButton && (
          <button
            onClick={handleCopy}
            aria-label="Copy code"
            className="flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium text-zinc-500 hover:text-zinc-200 transition-colors"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-400" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
        )}
      </div>

      {/* Code */}
      <div className="overflow-x-auto">
        <pre className="p-4 text-[13px] leading-relaxed">
          <code className="font-mono">
            {lines.map((line, i) => (
              <div key={i} className="flex">
                {showLineNumbers && (
                  <span className="w-8 shrink-0 select-none pr-4 text-right text-[11px] leading-relaxed text-zinc-600">
                    {i + 1}
                  </span>
                )}
                <span className="whitespace-pre text-zinc-300">{line}</span>
              </div>
            ))}
          </code>
        </pre>
      </div>
    </div>
  );
}

export function InlineCode({ children }: { children: ReactNode }) {
  return (
    <code className="rounded-md border border-zinc-200 bg-zinc-100 px-1.5 py-0.5 font-mono text-[13px] font-medium text-zinc-800 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">
      {children}
    </code>
  );
}