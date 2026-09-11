import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
                <svg viewBox="0 0 32 32" fill="none" className="h-4 w-4">
                  <path d="M8 16L14 10L20 16L14 22Z" fill="white" opacity="0.9" />
                  <path d="M14 16L20 10L26 16L20 22Z" fill="white" opacity="0.6" />
                </svg>
              </div>
              <span className="font-bold text-neutral-900 dark:text-white">lfhai</span>
            </Link>
            <p className="text-sm text-neutral-500 dark:text-neutral-400 max-w-xs">
              Local-first heterogeneous AI runtime. Coordinate mismatched hardware into a unified inference system.
            </p>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Product</h4>
            <ul className="space-y-2 text-sm text-neutral-500 dark:text-neutral-400">
              <li><Link href="/docs" className="hover:text-neutral-900 dark:hover:text-white transition-colors">Documentation</Link></li>
              <li><Link href="/docs/quickstart" className="hover:text-neutral-900 dark:hover:text-white transition-colors">Quickstart</Link></li>
              <li><Link href="/docs/install" className="hover:text-neutral-900 dark:hover:text-white transition-colors">Installation</Link></li>
              <li><Link href="/docs/cli" className="hover:text-neutral-900 dark:hover:text-white transition-colors">CLI Reference</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Resources</h4>
            <ul className="space-y-2 text-sm text-neutral-500 dark:text-neutral-400">
              <li><Link href="/docs/architecture" className="hover:text-neutral-900 dark:hover:text-white transition-colors">Architecture</Link></li>
              <li><Link href="/docs/api" className="hover:text-neutral-900 dark:hover:text-white transition-colors">API Reference</Link></li>
              <li><Link href="/docs/configuration" className="hover:text-neutral-900 dark:hover:text-white transition-colors">Configuration</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Community</h4>
            <ul className="space-y-2 text-sm text-neutral-500 dark:text-neutral-400">
              <li><a href="https://github.com/your-org/lfhai" className="hover:text-neutral-900 dark:hover:text-white transition-colors" target="_blank" rel="noopener noreferrer">GitHub</a></li>
              <li><a href="https://github.com/your-org/lfhai/issues" className="hover:text-neutral-900 dark:hover:text-white transition-colors" target="_blank" rel="noopener noreferrer">Issues</a></li>
            </ul>
          </div>
        </div>
        <div className="mt-10 pt-6 border-t border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-neutral-400 dark:text-neutral-500">
            &copy; 2026 lfhai. MIT License.
          </p>
          <div className="flex items-center gap-4 text-xs text-neutral-400 dark:text-neutral-500">
            <Link href="/docs" className="hover:text-neutral-600 dark:hover:text-neutral-300">Docs</Link>
            <a href="https://github.com/your-org/lfhai" className="hover:text-neutral-600 dark:hover:text-neutral-300" target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
