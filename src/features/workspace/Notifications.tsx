import { useState } from "react";
import { Link } from "react-router-dom";
import { Bell, CheckCheck, ChevronRight } from "lucide-react";
import { api, type Home } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import {
  localDay,
  updateWorkspace,
  useWorkspace,
} from "../../lib/learnerWorkspace";
import { LoadError } from "../../components/Status";

interface NotificationItem {
  id: string;
  type: "cards" | "exam" | "system";
  badge: string;
  time: string;
  title: string;
  text: string;
  path: string;
}

export function Notifications() {
  const w = useWorkspace(),
    [filter, setFilter] = useState<"all" | "unread">("all");
  const { data, error, reload } = useLoad(() => api.get<Home>("/home"), []);

  const notices: NotificationItem[] = [
    ...(w.remind && data?.due_cards
      ? [
          {
            id: `due:${localDay()}:${data.due_cards}`,
            type: "cards" as const,
            badge: "Ôn tập thẻ",
            time: "Hôm nay",
            title: `${data.due_cards} thẻ đang đến hạn`,
            text: "Mở phiên ôn các thẻ đến hạn hôm nay.",
            path: "/luyen-tap/on-the",
          },
        ]
      : []),
    ...w.activity
      .filter((a) => a.kind === "exam")
      .slice(-5)
      .reverse()
      .map((a, idx) => ({
        id: a.id,
        type: "exam" as const,
        badge: "Thi thử",
        time: idx === 0 ? "Gần đây" : "Đã nộp",
        title: "Đã nộp bài thi thử",
        text: "Kết quả đã sẵn sàng. Xem lại điểm và các câu cần ôn.",
        path: `/thi-thu/ket-qua/${a.id.split(":").at(-1)}`,
      })),
  ];

  const unreadCount = notices.filter((n) => !w.read.includes(n.id)).length;
  const rows = notices.filter(
    (n) => filter !== "unread" || !w.read.includes(n.id),
  );

  return (
    <div className="screen stack notifications-page">
      <header className="page-heading">
        <h1>Thông báo</h1>
        <p>Nhắc ôn tập và cập nhật kết quả học của bạn.</p>
      </header>

      <div className="notifications-toolbar">
        <div className="segmented">
          <button
            type="button"
            className={filter === "all" ? "active" : ""}
            onClick={() => setFilter("all")}
          >
            Tất cả
            <span className="notif-pill-badge">{notices.length}</span>
          </button>
          <button
            type="button"
            className={filter === "unread" ? "active" : ""}
            onClick={() => setFilter("unread")}
          >
            Chưa đọc
            <span
              className={`notif-pill-badge ${unreadCount > 0 ? "has-unread" : ""}`}
            >
              {unreadCount}
            </span>
          </button>
        </div>

        <button
          type="button"
          className="notification-mark-all"
          disabled={unreadCount === 0}
          onClick={() =>
            updateWorkspace((w) => ({
              ...w,
              read: [...new Set([...w.read, ...notices.map((n) => n.id)])],
            }))
          }
        >
          <CheckCheck size={18} />
          <span>{unreadCount === 0 ? "Đã đọc tất cả" : "Đọc tất cả"}</span>
        </button>
      </div>

      {error && <LoadError message={error} onRetry={reload} />}

      <section className="notification-list" aria-label="Danh sách thông báo">
        {rows.map((n) => {
          const isUnread = !w.read.includes(n.id);
          return (
            <Link
              key={n.id}
              className={`notification-item ${isUnread ? "is-unread" : ""}`}
              to={n.path}
              onClick={() =>
                updateWorkspace((w) => ({
                  ...w,
                  read: [...new Set([...w.read, n.id])],
                }))
              }
            >
              <div className="notification-copy">
                <p className="notification-meta">
                  {n.badge}
                  <span>{n.time}</span>
                </p>
                <h2>
                  {isUnread && (
                    <span className="notification-dot" aria-label="Chưa đọc" />
                  )}
                  {n.title}
                </h2>
                <p className="notification-description">{n.text}</p>
                <span className="notification-action">
                  {n.type === "cards" ? "Ôn thẻ" : "Xem kết quả"}
                </span>
              </div>
              <ChevronRight size={18} aria-hidden="true" />
            </Link>
          );
        })}

        {!rows.length && (
          <div className="notif-empty-state">
            <div className="notif-empty-icon">
              <Bell size={28} />
            </div>
            <h3>Không có thông báo mới</h3>
            <p>
              {filter === "unread"
                ? "Bạn đã đọc hết tất cả thông báo. Chuyển sang tab 'Tất cả' để xem lịch sử."
                : "Các thẻ đến hạn ôn tập và bài thi thử đã nộp sẽ xuất hiện tại đây."}
            </p>
            {filter === "unread" && notices.length > 0 ? (
              <button
                type="button"
                className="btn secondary"
                onClick={() => setFilter("all")}
              >
                Xem tất cả thông báo
              </button>
            ) : (
              <Link to="/luyen-tap/on-the" className="btn primary">
                Bắt đầu ôn thẻ ngay
              </Link>
            )}
          </div>
        )}
      </section>

      <section
        className="notification-settings"
        aria-labelledby="notification-settings-heading"
      >
        <h2 id="notification-settings-heading">Tùy chọn thông báo</h2>
        <label
          className="notification-preference"
          htmlFor="remind-cards-toggle"
        >
          <span>
            <strong>Nhắc ôn thẻ đến hạn</strong>
            <small>Hiển thị lời nhắc trong ứng dụng.</small>
          </span>
          <span className="notif-toggle-switch">
            <input
              id="remind-cards-toggle"
              type="checkbox"
              checked={w.remind}
              onChange={(e) =>
                updateWorkspace((w) => ({ ...w, remind: e.target.checked }))
              }
            />
            <span className="notif-toggle-slider" />
          </span>
        </label>
        <p className="muted small">
          Lời nhắc xuất hiện khi mở ứng dụng trên thiết bị này. Chưa gửi thông
          báo đẩy hoặc email.
        </p>
      </section>
    </div>
  );
}
