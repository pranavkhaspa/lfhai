import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "lfhai — Local-First Heterogeneous AI Runtime",
    template: "%s · lfhai",
  },
  description:
    "One OpenAI-compatible API that spreads AI inference across your GPUs, CPUs, and edge devices. Local-first, private, no accounts.",
  openGraph: {
    title: "lfhai — Local-First Heterogeneous AI Runtime",
    description:
      "One API. Every machine. Spread AI inference across the hardware you already own.",
  },
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
      <body
        className={`${inter.variable} ${jetbrains.variable} min-h-screen bg-white font-sans text-zinc-950 antialiased dark:bg-zinc-950 dark:text-zinc-200`}
      >
        {children}
      </body>
    </html>
  );
}