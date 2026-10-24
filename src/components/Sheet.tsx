import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";
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
  callback.current = onClose;
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
          hidden={!open}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={onClose}
        >
          <motion.div
            ref={panel}
            tabIndex={-1}
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            transition={{ duration: 0.2 }}
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
