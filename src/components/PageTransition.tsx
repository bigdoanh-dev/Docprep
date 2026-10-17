import { useLayoutEffect, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useLocation, useOutlet } from "react-router-dom";

function PageFrame({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, []);
  return <>{children}</>;
}

/** Capture each outlet so an exiting page retains its own route content. */
export function PageTransition({
  context,
  className,
}: {
  context?: unknown;
  className?: string;
}) {
  const outlet = useOutlet(context);
  const { pathname } = useLocation();
  const reduced = useReducedMotion();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={pathname}
        className={className}
        initial={{ opacity: 0, y: reduced ? 0 : 14 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: reduced ? 0 : -8 }}
        transition={{ duration: reduced ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
      >
        <PageFrame>{outlet}</PageFrame>
      </motion.div>
    </AnimatePresence>
  );
}
