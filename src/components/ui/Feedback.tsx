import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
type Notice = { id: number; kind: "success" | "error" | "info"; text: string };
type NotifyFn = {
  (text: string, kind?: Notice["kind"]): void;
  dismiss?: () => void;
};
const FeedbackContext = createContext<NotifyFn>(() => {});
export function useFeedback() {
  return useContext(FeedbackContext);
}
export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<Notice[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setNotices([]);
  }, []);

  const notify: NotifyFn = useCallback(
    (text: string, kind: Notice["kind"] = "success") => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      const id = Date.now();
      // Replace previous toast immediately (single active toast, no stacking)
      setNotices([{ id, text, kind }]);
      // Auto-hide promptly after 2200ms
      timerRef.current = setTimeout(() => {
        setNotices([]);
      }, 2200);
    },
    [],
  );
  notify.dismiss = dismiss;

  return (
    <FeedbackContext.Provider value={notify}>
      {children}
      <div className="toast-stack" aria-live="polite">
        <AnimatePresence mode="popLayout">
          {notices.map((n) => (
            <motion.div
              key={n.id}
              className={`toast ${n.kind}`}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.12 }}
            >
              <span>
                {n.kind === "success" ? (
                  <CheckCircle2 size={16} />
                ) : n.kind === "error" ? (
                  <AlertCircle size={16} />
                ) : (
                  <Info size={16} />
                )}
              </span>
              <p>{n.text}</p>
              <button
                className="icon-btn"
                aria-label="Đóng thông báo"
                onClick={dismiss}
              >
                <X size={15} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </FeedbackContext.Provider>
  );
}
