"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import clsx from "clsx";

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  showLineNumbers?: boolean;
  copyButton?: boolean;
}

export function CodeBlock({
  code,
  language = "bash",
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
    <div className="group relative rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-950 dark:bg-neutral-900 overflow-hidden my-6">
      {/* Header */}
      {(filename || copyButton) && (
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-neutral-800 bg-neutral-900 dark:bg-neutral-950">
          <div className="flex items-center gap-2">
            {filename && (
              <span className="text-xs font-medium text-neutral-400 font-mono">
                {filename}
              </span>
            )}
          </div>
          {copyButton && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  Copy
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* Code */}
      <div className="overflow-x-auto">
        <pre className="p-4 text-sm leading-relaxed">
          <code>
            {lines.map((line, i) => (
              <div key={i} className="flex">
                {showLineNumbers && (
                  <span className="inline-block w-8 text-right pr-4 text-neutral-600 select-none text-xs leading-relaxed">
                    {i + 1}
                  </span>
                )}
                <span className="text-neutral-300">{line}</span>
              </div>
            ))}
          </code>
        </pre>
      </div>
    </div>
  );
}

export function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded-md bg-neutral-100 dark:bg-neutral-800 px-1.5 py-0.5 text-sm font-mono font-medium text-brand-700 dark:text-brand-300 border border-neutral-200 dark:border-neutral-700">
      {children}
    </code>
  );
}
