import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { THEME_STORAGE_KEY } from "@/lib/constants";

export type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const THEME_COLOR: Record<Theme, string> = { dark: "#08090d", light: "#f5f6f8" };

export function ThemeProvider({ children }: { children: ReactNode }) {
  // index.html applies the stored theme before first paint; read what it chose.
  const [theme, setThemeState] = useState<Theme>(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  );

  const setTheme = useCallback((next: Theme) => {
    // Flip the class before the state update so anything reading computed CSS
    // variables during the re-render (chart colours) sees the new palette.
    document.documentElement.classList.toggle("dark", next === "dark");
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[next]);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Storage can be unavailable (private mode); the theme still applies for this session.
    }
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(
    () => setTheme(theme === "dark" ? "light" : "dark"),
    [setTheme, theme],
  );

  const value = useMemo(() => ({ theme, setTheme, toggleTheme }), [theme, setTheme, toggleTheme]);

  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
