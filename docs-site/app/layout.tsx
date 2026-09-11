import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "lfhai - Local-First Heterogeneous AI Runtime",
  description:
    "Coordinate mismatched consumer hardware into a unified AI inference system. Route LLM tasks across GPU nodes, CPU servers, and edge devices.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </head>
      <body className="min-h-screen bg-white dark:bg-neutral-950 antialiased">
        {children}
      </body>
    </html>
  );
}
