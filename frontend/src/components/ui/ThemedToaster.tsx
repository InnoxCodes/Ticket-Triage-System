import type { CSSProperties } from "react";
import { Toaster } from "sonner";

import { useTheme } from "@/context/ThemeContext";

// Sonner exposes its palette as CSS variables; pointing them at the design
// tokens keeps toasts on-theme in both modes without fighting its stylesheet.
const TOKEN_STYLE = {
  "--normal-bg": "var(--surface)",
  "--normal-border": "var(--line-strong)",
  "--normal-text": "var(--fg)",
  "--border-radius": "12px",
} as CSSProperties;

export function ThemedToaster() {
  const { theme } = useTheme();

  return (
    <Toaster
      theme={theme}
      position="bottom-right"
      closeButton
      visibleToasts={4}
      style={TOKEN_STYLE}
      toastOptions={{
        classNames: {
          toast: "font-sans shadow-overlay!",
          description: "text-fg-muted!",
        },
      }}
    />
  );
}
