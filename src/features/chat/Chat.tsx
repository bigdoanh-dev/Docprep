import {
  BookOpenText,
  History,
  MessageSquareText,
  SquarePen,
  Search,
  X,
  ArrowLeft,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Conversation } from "../../components/Conversation";
import { LoadError } from "../../components/Status";
import { api, type ChatSessionSummary, type Listed } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { useLoad } from "../../lib/hooks";
import { useActor } from "../../app/identity";
import { updateWorkspace, useWorkspace } from "../../lib/learnerWorkspace";
const STARTERS = [
  "Phân biệt tỷ lệ hiện mắc và tỷ lệ mới mắc",
  "Nghiên cứu cắt ngang đo chỉ số nào?",
  "Nguy cơ tương đối được hiểu như thế nào?",
];
export function Chat({
  embedded = false,
  onClose,
  expanded = false,
  onToggleSize,
}: {
  embedded?: boolean;
  onClose?: () => void;
  expanded?: boolean;
  onToggleSize?: () => void;
}) {
  const actor = useActor();
  const [query, setQuery] = useState("");
  const [newChatVersion, setNewChatVersion] = useState(0);
  const [params] = useSearchParams(),
    loc = useLocation(),
    navigate = useNavigate(),
    [tick, setTick] = useState(0),
    w = useWorkspace();
  const [localId, setLocalId] = useState<number | null>(() => {
    const saved = new URLSearchParams(w.lastChatSearch ?? "").get("s");
    return saved ? Number(saved) : null;
  });
  const [historyOpen, setHistoryOpen] = useState(false);
  const id = embedded
    ? localId
    : params.get("s")
      ? Number(params.get("s"))
      : null;
  const selectSession = (sid: number | null, replace = false) => {
    const search = sid ? `?s=${sid}` : "";
    updateWorkspace((prev) => ({ ...prev, lastChatSearch: search || null }));
    if (embedded) setLocalId(sid);
    else navigate(`/hoi-dap${search}`, { replace });
    setHistoryOpen(false);
    setQuery("");
  };

  useEffect(() => {
    if (id !== null && Number.isFinite(id) && id > 0) {
      const search = `?s=${id}`;
      updateWorkspace((prev) => {
        if (prev.lastChatSearch === search) return prev;
        return { ...prev, lastChatSearch: search };
      });
    } else if (!embedded && loc.pathname === "/hoi-dap" && !loc.search) {
      updateWorkspace((prev) => {
        if (!prev.lastChatSearch) return prev;
        return { ...prev, lastChatSearch: null };
      });
    }
  }, [id, loc.pathname, loc.search, embedded]);
  const { data, error, reload } = useLoad(
    () =>
      api.get<Listed<ChatSessionSummary> & { next_cursor?: string | null }>(
        "/chat/sessions?limit=50",
      ),
    [tick],
  );
  const [older, setOlder] = useState<ChatSessionSummary[]>([]),
    [cursor, setCursor] = useState<string | null>(null),
    [moreBusy, setMoreBusy] = useState(false),
    [moreError, setMoreError] = useState("");
  const nextCursor = cursor ?? data?.next_cursor;
  const more = async () => {
    if (!nextCursor || moreBusy) return;
    setMoreBusy(true);
    setMoreError("");
    try {
      const page = await api.get<
        Listed<ChatSessionSummary> & { next_cursor?: string | null }
      >(`/chat/sessions?limit=50&cursor=${encodeURIComponent(nextCursor)}`);
      setOlder((prev) => [...prev, ...page.items]);
      setCursor(page.next_cursor ?? "");
    } catch (e) {
      setMoreError((e as Error).message);
    } finally {
      setMoreBusy(false);
    }
  };
  const sessions = [...(data?.items ?? []), ...older].filter(
    (s, i, a) => a.findIndex((x) => x.id === s.id) === i,
  );
  const matches = sessions.filter((s) =>
    s.title.toLocaleLowerCase("vi").includes(query.toLocaleLowerCase("vi")),
  );
  return (
    <div
      className={`tutor chat-page ${embedded ? "tutor-embedded" : "tutor-page"}`}
    >
      <header className="tutor-toolbar">
        <button
          type="button"
          className={`tutor-icon-button ${historyOpen ? "is-active" : ""}`}
          aria-label={historyOpen ? "Ẩn lịch sử" : "Lịch sử trò chuyện"}
          title="Lịch sử trò chuyện"
          aria-expanded={historyOpen}
          aria-controls={embedded ? "popup-history" : "page-history"}
          onClick={() => setHistoryOpen((v) => !v)}
        >
          {historyOpen ? <ArrowLeft size={19} /> : <History size={19} />}
        </button>
        <div className="tutor-identity">
          <span className="tutor-brand-mark">
            <BookOpenText size={20} />
          </span>
          <div>
            <h1>Gia sư AI</h1>
            <p>
              {actor?.mode === "demo"
                ? "Y học dự phòng · Minh họa"
                : "Hỏi đáp Y học dự phòng"}
            </p>
          </div>
        </div>
        <div className="tutor-toolbar-actions">
          <button
            type="button"
            className="tutor-icon-button"
            aria-label="Cuộc trò chuyện mới"
            title="Cuộc trò chuyện mới"
            onClick={() => {
              selectSession(null);
              setNewChatVersion((v) => v + 1);
            }}
          >
            <SquarePen size={19} />
          </button>
          {embedded && onToggleSize && (
            <button
              type="button"
              className="tutor-icon-button"
              aria-label={expanded ? "Thu gọn cửa sổ" : "Mở rộng cửa sổ"}
              title={expanded ? "Thu gọn cửa sổ" : "Mở rộng cửa sổ"}
              aria-pressed={expanded}
              onClick={onToggleSize}
            >
              {expanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button>
          )}
          {onClose && (
            <button
              type="button"
              className="tutor-icon-button"
              aria-label="Đóng Gia sư AI"
              title="Đóng"
              onClick={onClose}
            >
              <X size={20} />
            </button>
          )}
        </div>
      </header>
      <div className="chat-workspace tutor-workspace">
        <aside
          id={embedded ? "popup-history" : "page-history"}
          className="tutor-history"
          hidden={!historyOpen}
        >
          <div className="tutor-history-heading">
            <h2>Cuộc trò chuyện</h2>
            <span>{sessions.length}</span>
          </div>
          <label className="tutor-history-search">
            <Search size={17} />
            <input
              aria-label="Tìm cuộc trò chuyện"
              placeholder="Tìm trong lịch sử…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          {error && <LoadError message={error} onRetry={reload} />}
          {!data && !error && (
            <p role="status" className="tutor-history-empty">
              Đang tải lịch sử…
            </p>
          )}
          <div className="tutor-history-list">
            {matches.map((s) => (
              <button
                key={s.id}
                className={s.id === id ? "selected" : ""}
                onClick={() => selectSession(s.id)}
              >
                <MessageSquareText size={17} />
                <span>
                  <strong>{s.title}</strong>
                  <small>{formatDate(s.updated_at)}</small>
                </span>
              </button>
            ))}
          </div>
          {data && matches.length === 0 && (
            <p className="tutor-history-empty">
              {query
                ? "Không tìm thấy cuộc trò chuyện phù hợp."
                : "Chưa có cuộc trò chuyện. Hãy bắt đầu từ điều bạn muốn hiểu rõ hơn."}
            </p>
          )}
          {nextCursor && (
            <button className="tutor-more" onClick={more} disabled={moreBusy}>
              {moreBusy ? "Đang tải…" : "Xem thêm hội thoại"}
            </button>
          )}
          {moreError && (
            <p className="warn" role="alert">
              {moreError}
            </p>
          )}
        </aside>
        <section
          className="conversation-panel"
          hidden={historyOpen}
          aria-label="Nội dung hội thoại"
        >
          <Conversation
            key={newChatVersion}
            sessionId={id}
            starters={STARTERS}
            onSession={(sid) => {
              selectSession(sid, true);
              setTick((v) => v + 1);
            }}
          />
        </section>
      </div>
    </div>
  );
}
