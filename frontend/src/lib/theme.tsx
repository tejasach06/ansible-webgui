import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
type Theme = "light" | "dark" | "system";
const ThemeContext = createContext<{ theme: Theme; setTheme: (theme: Theme) => void; effectiveTheme: "light" | "dark" } | null>(null);
const readTheme = (): Theme => { const value = localStorage.getItem("awg-theme"); return value === "light" || value === "dark" || value === "system" ? value : "system"; };
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readTheme);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  const effectiveTheme = theme === "system" ? (systemDark ? "dark" : "light") : theme;
  useEffect(() => { const media = window.matchMedia("(prefers-color-scheme: dark)"); const onChange = () => setSystemDark(media.matches); media.addEventListener("change", onChange); return () => media.removeEventListener("change", onChange); }, []);
  useEffect(() => { document.documentElement.classList.toggle("dark", effectiveTheme === "dark"); }, [effectiveTheme]);
  const value = useMemo(() => ({ theme, effectiveTheme, setTheme: (next: Theme) => { localStorage.setItem("awg-theme", next); setThemeState(next); } }), [theme, effectiveTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
export function useTheme() { const value = useContext(ThemeContext); if (!value) throw new Error("useTheme must be used inside ThemeProvider"); return value; }
