import { AnimatePresence, motion } from "motion/react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";
// Only the topmost dialog handles Escape/Tab. Nested source drawers keep the body locked.
const dialogs: symbol[] = [];
let beforeOverflow = "";
export function Sheet({
  open,
  onClose,
  title,
  children,
  className = "",
  keepMounted = false,
  hideHeader = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  className?: string;
  keepMounted?: boolean;
  hideHeader?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null),
    callback = useRef(onClose);
  const [keepMountedVisible, setKeepMountedVisible] = useState(open);
  const isAssistant = className.split(/\s+/).includes("assistant-popup");
  callback.current = onClose;
  useLayoutEffect(() => {
    if (keepMounted && open) setKeepMountedVisible(true);
  }, [keepMounted, open]);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const id = Symbol(title);
    if (dialogs.length === 0) {
      beforeOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      const root = document.getElementById("root");
      if (root) root.inert = true;
    }
    dialogs.push(id);
    if (hideHeader) panel.current?.focus({ preventScroll: true });
    else panel.current?.querySelector<HTMLElement>("button,input")?.focus();
    const key = (e: KeyboardEvent) => {
      if (dialogs.at(-1) !== id) return;
      if (e.key === "Escape") callback.current();
      if (e.key !== "Tab") return;
      const nodes = [
        ...(panel.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled),a[href],input:not(:disabled),select,textarea,[tabindex="0"]',
        ) ?? []),
      ];
      if (!nodes.length) return;
      const first = nodes[0],
        last = nodes[nodes.length - 1];
      if (
        e.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === panel.current)
      ) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      const index = dialogs.indexOf(id);
      if (index >= 0) dialogs.splice(index, 1);
      if (dialogs.length === 0) {
        document.body.style.overflow = beforeOverflow;
        const root = document.getElementById("root");
        if (root) root.inert = false;
      }
      window.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [open]);
  return createPortal(
    <AnimatePresence>
      {(open || keepMounted) && (
        <motion.div
          className={`scrim ${className}`}
          hidden={keepMounted && !open && !keepMountedVisible}
          aria-hidden={keepMounted ? !open : undefined}
          inert={keepMounted ? !open : undefined}
          initial={keepMounted ? false : { opacity: 0 }}
          animate={{ opacity: open ? 1 : 0 }}
          exit={keepMounted ? undefined : { opacity: 0 }}
          transition={{ opacity: { duration: 0.22, ease: "easeOut" } }}
          style={keepMounted ? { pointerEvents: open ? "auto" : "none" } : undefined}
          onMouseDown={onClose}
        >
          <motion.div
            ref={panel}
            tabIndex={-1}
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-label={title}
            layout={keepMounted && isAssistant}
            initial={keepMounted ? { y: 24, opacity: 0 } : { x: 24, opacity: 0 }}
            animate={keepMounted ? (open ? { y: 0, opacity: 1 } : { y: 24, opacity: 0 }) : { x: 0, opacity: 1 }}
            exit={keepMounted ? undefined : { x: 24, opacity: 0 }}
            transition={
              keepMounted && isAssistant
                ? {
                    layout: { type: "spring", stiffness: 320, damping: 34 },
                    y: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
                    opacity: { duration: 0.18, ease: "easeOut" },
                    x: { duration: 0.2, ease: "easeOut" },
                  }
                : { duration: 0.2 }
            }
            onAnimationComplete={() => {
              if (keepMounted && !open) setKeepMountedVisible(false);
            }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            {!hideHeader && (
              <div className="sheet-head">
                <h2>{title}</h2>
                <button
                  className="icon-btn"
                  onClick={onClose}
                  aria-label="Đóng"
                >
                  <Icon name="close" />
                </button>
              </div>
            )}
            <div className="sheet-body">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
