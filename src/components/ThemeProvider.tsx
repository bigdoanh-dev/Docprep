import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
type Preference = "light" | "dark" | "system";
type Theme = "light" | "dark";
const KEY = "yhdp.theme.v1";
function readPreference(): Preference {
  try { const saved = localStorage.getItem(KEY); return saved === "light" || saved === "dark" ? saved : "system"; } catch { return "system"; }
}
const ThemeContext = createContext<{ theme: Theme; toggleTheme: () => void } | null>(null);
export function ThemeProvider({ children }: { children: ReactNode }) {
  const transition = useRef<ReturnType<Document["startViewTransition"]> | null>(null);
  const [preference, setPreference] = useState<Preference>(readPreference);
  const [systemDark, setSystemDark] = useState(() => matchMedia("(prefers-color-scheme: dark)").matches);
  const theme: Theme = preference === "system" ? systemDark ? "dark" : "light" : preference;
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#101b28" : "#ffffff");
  }, [theme]);
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const syncSystem = () => setSystemDark(media.matches);
    const syncStorage = (event: StorageEvent) => { if (event.key === KEY || event.key === null) setPreference(readPreference()); };
    media.addEventListener("change", syncSystem);
    window.addEventListener("storage", syncStorage);
    return () => { media.removeEventListener("change", syncSystem); window.removeEventListener("storage", syncStorage); };
  }, []);
  const toggleTheme = useCallback(() => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    try { localStorage.setItem(KEY, next); } catch { /* The switch also works when browser storage is unavailable. */ }
    const update = () => flushSync(() => setPreference(next));
    transition.current?.skipTransition();
    if (document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const current = document.startViewTransition(update);
      transition.current = current;
      void current.finished.catch(() => {}).finally(() => {
        if (transition.current === current) transition.current = null;
      });
    }
    else update();
  }, [theme]);
  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);
  return <ThemeContext value={value}>{children}</ThemeContext>;
}
export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("ThemeProvider is required.");
  return context;
}
