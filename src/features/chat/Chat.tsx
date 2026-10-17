import { MessageSquareText, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Conversation } from "../../components/Conversation";
import { MascotPickerSheet } from "../../components/MascotPicker";
import { LoadError } from "../../components/Status";
import { api, type ChatSessionSummary, type Listed } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { useLoad } from "../../lib/hooks";
import { updateWorkspace, useWorkspace } from "../../lib/learnerWorkspace";
const STARTERS = [
  "Phân biệt tỷ lệ hiện mắc và tỷ lệ mới mắc",
  "Nghiên cứu cắt ngang đo chỉ số nào?",
  "Nguy cơ tương đối được hiểu như thế nào?",
];
export function Chat() {
  const [params] = useSearchParams(),
    loc = useLocation(),
    navigate = useNavigate(),
    [tick, setTick] = useState(0),
    w = useWorkspace(),
    [mascotSheetOpen, setMascotSheetOpen] = useState(false);
  const id = params.get("s") ? Number(params.get("s")) : null;

  useEffect(() => {
    if (id !== null && Number.isFinite(id) && id > 0) {
      const search = `?s=${id}`;
      updateWorkspace((prev) => {
        if (prev.lastChatSearch === search) return prev;
        return { ...prev, lastChatSearch: search };
      });
    } else if (loc.pathname === "/hoi-dap" && !loc.search) {
      updateWorkspace((prev) => {
        if (!prev.lastChatSearch) return prev;
        return { ...prev, lastChatSearch: null };
      });
    }
  }, [id, loc.pathname, loc.search]);
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
  return (
    <div className="chat-page">
      <header className="page-heading chat-header">
        <div className="chat-header-top">
          <h1>Hỏi đáp học tập</h1>
          <button
            type="button"
            className="btn-change-companion"
            onClick={() => setMascotSheetOpen(true)}
            aria-label="Đổi bạn đồng hành"
            title="Đổi bạn đồng hành"
          >
            <span
              className="companion-thumb"
              aria-hidden="true"
              style={{
                backgroundImage: `url(/mobile/mascot-${w.mascot}-directions.png)`,
              }}
            />
            <span className="companion-label">Đổi bạn đồng hành</span>
          </button>
        </div>
        <p className="chat-header-desc">
          Bạn có thể hỏi điều chưa hiểu trong bài học bằng lời của mình. Phần
          trả lời tự động có thể sai; hãy mở tài liệu tham khảo để kiểm tra.
        </p>
      </header>
      <MascotPickerSheet
        open={mascotSheetOpen}
        onClose={() => setMascotSheetOpen(false)}
      />
      <div className="chat-workspace">
        <aside className="chat-history">
          <button
            className="btn block"
            onClick={() => {
              updateWorkspace((prev) => {
                if (!prev.lastChatSearch) return prev;
                return { ...prev, lastChatSearch: null };
              });
              navigate("/hoi-dap");
            }}
          >
            <Plus size={17} />
            Cuộc trò chuyện mới
          </button>
          <p className="muted small">Lịch sử hội thoại</p>
          {error && <LoadError message={error} onRetry={reload} />}
          <div>
            {sessions.map((s) => (
              <button
                key={s.id}
                className={s.id === id ? "selected" : ""}
                onClick={() => navigate(`/hoi-dap?s=${s.id}`)}
              >
                <MessageSquareText size={16} />
                <span>
                  <strong>{s.title}</strong>
                  <small>{formatDate(s.updated_at)}</small>
                </span>
              </button>
            ))}
          </div>
          {nextCursor && (
            <button className="btn" onClick={more} disabled={moreBusy}>
              {moreBusy ? "Đang tải…" : "Xem thêm hội thoại"}
            </button>
          )}
          {moreError && (
            <p className="warn" role="alert">
              {moreError}
            </p>
          )}
          <p className="chat-boundary">
            Hỏi về nội dung ôn tập. Không nhập thông tin định danh hoặc dữ liệu
            người bệnh.
          </p>
        </aside>
        <section className="conversation-panel">
          <Conversation
            sessionId={id}
            starters={STARTERS}
            onSession={(sid) => {
              navigate(`/hoi-dap?s=${sid}`, { replace: true });
              setTick((v) => v + 1);
            }}
          />
        </section>
      </div>
    </div>
  );
}
