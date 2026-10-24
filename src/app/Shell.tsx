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
import { useEffect, useState, type ReactNode } from "react";
import { Link, Outlet, useLocation, useOutletContext } from "react-router-dom";
import { signOut } from "../lib/api";
import { streak, useWorkspace } from "../lib/learnerWorkspace";
import { useActor } from "./identity";
import { Sheet } from "../components/Sheet";
import { Chat } from "../features/chat/Chat";
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
    [chatOpen, setChatOpen] = useState(false),
    [chatExpanded, setChatExpanded] = useState(false),
    [chatMounted, setChatMounted] = useState(false);

  useEffect(() => {
    window.scrollTo(0, 0);
    setChatOpen(false);
    setChatExpanded(false);
  }, [loc.pathname]);

  const exam = loc.pathname.startsWith("/thi-thu/lam-bai/");
  const cards = /bo-the|on-the|duyet-the|phien\/the/.test(loc.pathname);
  const immersive = loc.pathname === "/phien/dieu-chinh";

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
  const staffActive = loc.pathname.startsWith("/quan-ly/ket-qua")
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
      className={`mobile-app ${actor.role !== "learner" ? "staff-app" : ""} ${immersive ? "immersive-app" : ""}`}
    >
      {!immersive && (
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
                <span
                  className={`staff-role-pill ${actor.role === "admin" ? "admin" : ""}`}
                >
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
      )}
      <main
        id="main-content"
        className={`mobile-content route-${loc.pathname.split("/")[1] || "home"} ${actor.role !== "learner" ? "staff-content" : ""} ${immersive ? "immersive-content" : ""}`}
      >
        {!immersive && actor.mode === "demo" && (
          <p className="mobile-demo">Dữ liệu minh họa · lưu trên trình duyệt</p>
        )}
        {children ?? <Outlet context={context} />}
      </main>
      {!immersive && actor.role === "learner" ? (
        <>
          {loc.pathname !== "/hoi-dap" && (
            <AssistantLauncher
              mascot={w.mascot}
              onOpenChat={() => {
                setChatMounted(true);
                setChatExpanded(false);
                setChatOpen(true);
              }}
            />
          )}
          {chatMounted && (
            <Sheet
              open={chatOpen}
              onClose={() => setChatOpen(false)}
              title="Gia sư AI"
              className={`assistant-popup ${chatExpanded ? "is-expanded" : ""}`}
              keepMounted
              hideHeader
            >
              <Chat
                embedded
                expanded={chatExpanded}
                onToggleSize={() => setChatExpanded((value) => !value)}
                onClose={() => setChatOpen(false)}
              />
            </Sheet>
          )}
          <nav className="mobile-footer" aria-label="Điều hướng chính">
            {learnerTabs.map(([to, label, Icon]) => (
              <Link
                key={to}
                to={to}
                aria-current={learnerActive === to ? "page" : undefined}
              >
                <Icon
                  size={21}
                  strokeWidth={learnerActive === to ? 2.3 : 1.7}
                />
                <span>{label}</span>
              </Link>
            ))}
          </nav>
        </>
      ) : !immersive ? (
        <nav
          className="mobile-footer staff-footer"
          aria-label="Điều hướng cán bộ"
        >
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
      ) : null}
    </div>
  );
}
