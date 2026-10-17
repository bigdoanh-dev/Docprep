import { AnimatePresence, motion } from "motion/react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === "dark";
  const label = dark ? "Chuyển sang chế độ sáng" : "Chuyển sang chế độ tối";
  return <button type="button" className="theme-toggle" aria-label={label} aria-pressed={dark} title={label} onClick={toggleTheme}><AnimatePresence mode="wait" initial={false}><motion.span key={theme} initial={{ opacity: 0, rotate: -35, scale: .8 }} animate={{ opacity: 1, rotate: 0, scale: 1 }} exit={{ opacity: 0, rotate: 35, scale: .8 }} transition={{ duration: .14 }}>{dark ? <Sun size={20} strokeWidth={1.7} /> : <Moon size={20} strokeWidth={1.7} />}</motion.span></AnimatePresence></button>;
}
