import Link from "next/link";
import clsx from "clsx";

export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={clsx("group flex items-center gap-2.5", className)}>
      <Mark />
      <span className="text-[15px] font-semibold tracking-tight text-zinc-900 dark:text-white">
        lfhai
      </span>
    </Link>
  );
}

export function Mark({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex h-7 w-7 items-center justify-center rounded-md bg-zinc-900 dark:bg-zinc-100",
        className
      )}
    >
      <svg viewBox="0 0 32 32" fill="none" className="h-4 w-4">
        <circle cx="8" cy="24" r="3" fill="currentColor" className="text-brand-400" />
        <circle cx="24" cy="8" r="3" fill="currentColor" className="text-zinc-400" />
        <path
          d="M10 21.5 22 10.5"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          className="text-white dark:text-zinc-950"
        />
      </svg>
    </span>
  );
}