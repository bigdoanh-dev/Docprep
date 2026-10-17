import { useRef } from "react";
import {
  motion,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "motion/react";
export function HeroPhoto() {
  const target = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target,
    offset: ["start end", "end start"],
  });
  const offset = useTransform(scrollYProgress, [0, 1], [-16, 16]);
  const y = useSpring(offset, { stiffness: 100, damping: 28 });
  return (
    <div ref={target} className="vietnam-hero-photo">
      <motion.img
        src="/images/medical/vietnam-medical-hero.webp"
        alt="Đội ngũ bác sĩ và nhân viên y tế tại bệnh viện Việt Nam"
        fetchPriority="high"
        width={1680}
        height={1120}
        style={{ y: reduced ? 0 : y }}
      />
    </div>
  );
}
