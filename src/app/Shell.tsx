import {
  Bell,
  BookOpen,
  Flame,
  Home,
  Layers,
  BarChart3,
  UserRound,
  LogOut,
  LayoutDashboard,
  GraduationCap,
  ShieldCheck,
  Settings2,
} from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { Link, Outlet, useLocation, useNavigate, useOutletContext } from "react-router-dom";
import { signOut } from "../lib/api";
import { streak, useWorkspace } from "../lib/learnerWorkspace";
import { useActor } from "./identity";
import { AssistantLauncher } from "../components/AssistantLauncher";

const learnerTabs = [
  ["/", "Trang chủ", Home],
  ["/luyen-tap", "Học tập", BookOpen],
  ["/luyen-tap/bo-the", "Thẻ ôn tập", Layers],
  ["/tien-do", "Tiến độ", BarChart3],
  ["/profile", "Profile", UserRound],
] as const;

const ministryTabs = [
  ["/quan-ly", "Tổng hợp", LayoutDashboard],
  ["/quan-ly/ket-qua", "Học tập", GraduationCap],
  ["/quan-ly/an-toan", "An toàn", ShieldCheck],
  ["/profile", "Tài khoản", UserRound],
] as const;

const adminTabs = [
  ["/quan-ly", "Tổng hợp", LayoutDashboard],
  ["/quan-ly/ket-qua", "Học tập", GraduationCap],
  ["/quan-ly/an-toan", "An toàn", ShieldCheck],
  ["/quan-tri", "Vận hành", Settings2],
  ["/profile", "Tài khoản", UserRound],
] as const;

export function Shell({ children }: { children?: ReactNode } = {}) {
  const context = useOutletContext(),
    actor = useActor()!,
    w = useWorkspace(),
    loc = useLocation(),
    navigate = useNavigate();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [loc.pathname]);

  const exam = loc.pathname.startsWith("/thi-thu/lam-bai/");
  const cards = /bo-the|on-the|duyet-the|phien\/the/.test(loc.pathname);

  // Active tab determination for learner
  const learnerActive =
    loc.pathname === "/"
      ? "/"
      : cards
        ? "/luyen-tap/bo-the"
        : loc.pathname.startsWith("/tien-do")
          ? "/tien-do"
          : loc.pathname === "/profile"
            ? "/profile"
            : "/luyen-tap";

  // Active tab determination for staff
  const staffActive =
    loc.pathname.startsWith("/quan-ly/ket-qua")
      ? "/quan-ly/ket-qua"
      : loc.pathname.startsWith("/quan-ly/an-toan")
        ? "/quan-ly/an-toan"
        : loc.pathname.startsWith("/quan-tri")
          ? "/quan-tri"
          : loc.pathname === "/profile"
            ? "/profile"
            : "/quan-ly";

  if (exam)
    return (
      <main id="main-content" className="exam-shell">
        <p className="demo-strip">
          {actor.mode === "demo" && "Bài thi minh họa · "}Thời gian tiếp tục
          chạy khi rời trang.
        </p>
        <Outlet context={context} />
      </main>
    );

  const staffNavTabs = actor.role === "admin" ? adminTabs : ministryTabs;

  return (
    <div
      className={`mobile-app ${actor.role !== "learner" ? "staff-app" : ""}`}
    >
      <header className="mobile-header">
        <Link
          to={actor.role === "learner" ? "/" : "/quan-ly"}
          className="mobile-brand"
        >
          <strong>DocPrep</strong>
          <span>
            {actor.role === "admin"
              ? "Quản trị YHDP"
              : actor.role === "ministry_viewer"
                ? "Báo cáo cấp Bộ"
                : "Ôn thi YHDP"}
          </span>
        </Link>
        <div className="header-actions">
          {actor.role === "learner" ? (
            <>
              <Link
                to="/tien-do/nhip-hoc"
                className="streak-badge"
                aria-label={`Chuỗi ôn tập ${streak(w.activity.map((a) => a.date))} ngày`}
              >
                <Flame size={18} fill="currentColor" />
                {streak(w.activity.map((a) => a.date))}
              </Link>
              <Link
                className="header-bell"
                to="/thong-bao"
                aria-label="Thông báo"
              >
                <Bell size={23} />
              </Link>
            </>
          ) : (
            <div className="staff-header-controls">
              <span className={`staff-role-pill ${actor.role === "admin" ? "admin" : ""}`}>
                {actor.role === "admin" ? "Quản trị" : "Cán bộ Bộ"}
              </span>
              <button
                className="header-bell staff-signout-btn"
                onClick={() => signOut()}
                aria-label="Đăng xuất"
                title="Đăng xuất khỏi phiên làm việc"
              >
                <LogOut size={16} />
              </button>
            </div>
          )}
        </div>
      </header>
      <main
        id="main-content"
        className={`mobile-content route-${loc.pathname.split("/")[1] || "home"} ${actor.role !== "learner" ? "staff-content" : ""}`}
      >
        {actor.mode === "demo" && (
          <p className="mobile-demo">Dữ liệu minh họa · lưu trên trình duyệt</p>
        )}
        {children ?? <Outlet context={context} />}
      </main>
      {actor.role === "learner" ? (
        <>
          <AssistantLauncher
            mascot={w.mascot}
            onOpenChat={() => {
              if (loc.pathname === "/hoi-dap") {
                const input = document.querySelector<HTMLInputElement>(
                  ".conversation-panel input",
                );
                input?.focus();
                return;
              }
              const target = w.lastChatSearch
                ? `/hoi-dap${w.lastChatSearch}`
                : "/hoi-dap";
              navigate(target);
            }}
          />
          <nav className="mobile-footer" aria-label="Điều hướng chính">
            {learnerTabs.map(([to, label, Icon]) => (
              <Link
                key={to}
                to={to}
                aria-current={learnerActive === to ? "page" : undefined}
              >
                <Icon size={21} strokeWidth={learnerActive === to ? 2.3 : 1.7} />
                <span>{label}</span>
              </Link>
            ))}
          </nav>
        </>
      ) : (
        <nav className="mobile-footer staff-footer" aria-label="Điều hướng cán bộ">
          {staffNavTabs.map(([to, label, Icon]) => {
            const isCurrent = staffActive === to;
            return (
              <Link
                key={to}
                to={to}
                aria-current={isCurrent ? "page" : undefined}
              >
                <Icon size={20} strokeWidth={isCurrent ? 2.4 : 1.7} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
