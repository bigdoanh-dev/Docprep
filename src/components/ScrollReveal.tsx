import { useEffect, useRef, type ReactNode } from "react";

export function ScrollReveal({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node || !("IntersectionObserver" in window)) return;
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let observer: IntersectionObserver | undefined;
    const setup = () => {
      observer?.disconnect();
      node.classList.remove("reveal-pending", "reveal-visible");
      if (preference.matches) return;
      // A zero threshold works for tall sections as well as small cards.
      node.classList.add("reveal-pending");
      observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            node.classList.add("reveal-visible");
          } else {
            // Prepare the next entrance from the edge the reader is approaching.
            node.style.setProperty(
              "--reveal-offset",
              entry.boundingClientRect.top < 0 ? "-18px" : "24px",
            );
            node.classList.remove("reveal-visible");
          }
        },
        { threshold: 0, rootMargin: "0px 0px -24px 0px" },
      );
      observer.observe(node);
    };
    setup();
    preference.addEventListener("change", setup);
    return () => {
      observer?.disconnect();
      preference.removeEventListener("change", setup);
      node.classList.remove("reveal-pending", "reveal-visible");
    };
  }, []);
  return (
    <div ref={ref} className={`scroll-reveal ${className}`}>
      {children}
    </div>
  );
}
