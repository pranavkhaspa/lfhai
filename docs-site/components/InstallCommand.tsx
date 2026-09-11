"use client";

import { useEffect, useState } from "react";
import { TerminalBlock, type TerminalVariant } from "./TerminalBlock";

interface InstallCommandProps {
  label?: string;
  variant?: TerminalVariant;
}

/**
 * Renders a curl install command that auto-detects the current site domain.
 * If the domain changes (e.g. lfhai.vercel.app -> lfhai.dev), the command
 * updates automatically - no hardcoded URLs.
 */
export function InstallCommand({
  label = "Install lfhai",
  variant = "accent",
}: InstallCommandProps) {
  const [origin, setOrigin] = useState("your-domain");

  useEffect(() => {
    setOrigin(window.location.origin);
  }, []);

  const command = `curl -fsSL ${origin}/install.sh | bash`;

  return (
    <TerminalBlock command={command} label={label} variant={variant}>
      <span className="sr-only">Install with: curl -fsSL [current-domain]/install.sh | bash</span>
    </TerminalBlock>
  );
}

export function useInstallUrl(): string {
  const [origin, setOrigin] = useState("https://your-domain");
  useEffect(() => {
    setOrigin(window.location.origin);
  }, []);
  return `${origin}/install.sh`;
}