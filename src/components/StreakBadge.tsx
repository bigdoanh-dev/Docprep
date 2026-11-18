import { Flame } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, LEARNING_UPDATED, type ProgressRhythm } from "../lib/api";

type Status =
  { kind: "loading" } | { kind: "error" } | { kind: "ready"; days: number };

function Badge({ status }: { status: Status }) {
  const label =
    status.kind === "ready"
      ? `Chuỗi ôn tập ${status.days} ngày`
      : status.kind === "loading"
        ? "Đang tải chuỗi ôn tập"
        : "Không tải được chuỗi ôn tập. Mở nhịp học để thử lại.";
  return (
    <Link
      to="/tien-do/nhip-hoc"
      className="streak-badge"
      aria-label={label}
      title={label}
      aria-busy={status.kind === "loading"}
    >
      <Flame size={18} fill="currentColor" />
      <span>
        {status.kind === "ready"
          ? status.days
          : status.kind === "loading"
            ? "…"
            : "—"}
      </span>
    </Link>
  );
}

function LiveStreak() {
  const { pathname } = useLocation();
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  useEffect(() => {
    let alive = true,
      generation = 0;
    async function refresh() {
      const current = ++generation;
      setStatus({ kind: "loading" });
      try {
        const data = await api.get<ProgressRhythm>("/progress/rhythm");
        if (!Number.isInteger(data.streak_days) || data.streak_days < 0)
          throw new Error("Invalid streak");
        if (alive && generation === current)
          setStatus({ kind: "ready", days: data.streak_days });
      } catch {
        if (alive && generation === current) setStatus({ kind: "error" });
      }
    }
    const visibleRefresh = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    void refresh();
    window.addEventListener(LEARNING_UPDATED, visibleRefresh);
    window.addEventListener("focus", visibleRefresh);
    const timer = window.setInterval(visibleRefresh, 60_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener(LEARNING_UPDATED, visibleRefresh);
      window.removeEventListener("focus", visibleRefresh);
    };
  }, [pathname]);
  return <Badge status={status} />;
}

/** Demo keeps its own behavior; live never substitutes a local/demo value. */
export function StreakBadge({ demoDays }: { demoDays?: number }) {
  return demoDays === undefined ? (
    <LiveStreak />
  ) : (
    <Badge status={{ kind: "ready", days: demoDays }} />
  );
}
