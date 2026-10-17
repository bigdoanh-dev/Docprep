import { GraduationCap } from "lucide-react";
export function AiStar({
  size = 20,
  onDark = false,
}: {
  size?: number;
  onDark?: boolean;
}) {
  return (
    <GraduationCap
      size={size}
      strokeWidth={1.7}
      aria-hidden="true"
      style={{ flexShrink: 0, color: onDark ? "#cfe5ff" : "var(--primary)" }}
    />
  );
}
