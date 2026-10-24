import { BookOpenText, Copy, Check } from "lucide-react";
import { ReportIssue } from "./ReportIssue";
import { useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  api,
  type ChatSuggestion,
  type Citation,
  type SuggestionAccepted,
} from "../lib/api";
import { chipLabel, type TurnView } from "../lib/chatTurn";
import { dayMonth } from "../lib/format";
import { AiStar } from "./AiStar";
import { AnswerText, CitationChip } from "./Answer";
import { Icon } from "./Icon";

// In a chat opened from a quiz item: where "Quay lại bài luyện" goes.
export type QuizContext = { back: string };

// One answer of Hỏi đáp (handover/06-screens.md, "Chat states"). Everything shown comes from this
// answer's events or its stored message: the steps that ran, what was checked, where it searched.
export function AssistantTurn({
  view,
  latest,
  busy,
  quiz,
  onCite,
  onExplainMore,
  onAskAnother,
  onClarify,
  onRetry,
}: {
  view: TurnView;
  latest: boolean;
  busy: boolean;
  quiz?: QuizContext;
  onCite: (c: Citation) => void;
  onExplainMore: () => void;
  onAskAnother: () => void;
  onClarify: (query: string, messageId: number) => void;
  onRetry: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  if (view.phase === "queued") {
    return (
      <div className="card stack" role="status">
        <p className="row h2" style={{ gap: 10 }}>
          <span className="spinner" />
          Đang xếp hàng · vị trí {view.position ?? "…"}
        </p>
        <p className="muted">
          Nhiều người đang hỏi. Câu hỏi của bạn vẫn giữ chỗ.
        </p>
      </div>
    );
  }
  if (view.phase === "working") return <WorkBox view={view} />;
  if (view.phase === "failed") {
    return (
      <div className="card stack" role="alert">
        <p>{view.error}</p>
        {latest && (
          <div>
            <button className="btn" onClick={onRetry} disabled={busy}>
              Thử lại
            </button>
          </div>
        )}
      </div>
    );
  }

  const result = {
    state: view.state ?? "insufficient_evidence",
    text: view.text ?? "",
    citations: view.citations,
    notice: view.notice,
  };
  return (
    <>
      {chipLabel(view) && <TraceChip view={view} />}
      {view.state === "answered" && (
        <div className="card stack tutor-answer">
          <div className="tutor-answer-author">
            <BookOpenText size={15} />
            Gia sư AI
          </div>
          <AnswerText result={result} onCite={onCite} />
          {view.citations.length > 0 && (
            <details className="tutor-sources">
              <summary>
                <BookOpenText size={14} />
                {view.citations.length} nguồn tham khảo
              </summary>
              <div>
                {view.citations.map((c) => (
                  <CitationChip
                    key={c.passage_id}
                    citation={c}
                    label={c.document}
                    onOpen={onCite}
                  />
                ))}
              </div>
            </details>
          )}
          {view.notice && (
            <details className="tutor-answer-notice">
              <summary>Lưu ý về câu trả lời</summary>
              <p>{view.notice}</p>
            </details>
          )}
          <div
            className="row tutor-answer-actions"
            style={{
              borderTop: "1px solid var(--divider)",
              paddingTop: 12,
              flexWrap: "wrap",
            }}
          >
            {quiz ? (
              <QuizActions back={quiz.back} suggestions={view.suggestions} />
            ) : (
              latest && (
                <button className="btn" onClick={onExplainMore} disabled={busy}>
                  Giải thích thêm
                </button>
              )
            )}
            <span className="grow" />
            <button
              type="button"
              className="tutor-icon-button"
              aria-label={copied ? "Đã sao chép" : "Sao chép câu trả lời"}
              title={copied ? "Đã sao chép" : "Sao chép"}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(view.text ?? "");
                  setCopied(true);
                  setCopyError("");
                } catch {
                  setCopyError(
                    "Chưa thể sao chép. Bạn có thể chọn phần văn bản cần dùng.",
                  );
                }
              }}
            >
              {copied ? <Check size={16} /> : <Copy size={16} />}
            </button>

            {view.messageId !== null && (
              <>
                <Helpful messageId={view.messageId} initial={view.helpful} />
                <ReportIssue
                  id={String(view.messageId)}
                  title="Câu trả lời của gia sư AI"
                  target="answer"
                />
              </>
            )}
          </div>
          {copyError && (
            <p role="status" className="muted small">
              {copyError}
            </p>
          )}
        </div>
      )}
      {view.state === "insufficient_evidence" && (
        <div className="card stack">
          <p style={{ fontSize: 16 }}>{view.text}</p>
          {view.notice && <p className="note">{view.notice}</p>}
          {view.searched.length > 0 && (
            <div>
              <p className="label">Đã tìm ở:</p>
              <ul
                aria-label="Đã tìm ở"
                style={{
                  margin: "4px 0 0",
                  paddingLeft: 20,
                  color: "var(--text-2)",
                }}
              >
                {view.searched.map((s) => (
                  <li key={s.document}>
                    {s.document}, {s.range}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {view.nearestChapter && (
              <button
                className="btn"
                onClick={() =>
                  onCite({
                    n: 1,
                    passage_id: view.nearestChapter!.passage_id,
                    document: view.nearestChapter!.label_vi,
                    chapter: null,
                    section: null,
                    page: null,
                    article: null,
                  })
                }
              >
                Mở {view.nearestChapter.label_vi}
              </button>
            )}
            <button className="btn" disabled>
              Gửi chuyên gia · R2
            </button>
            {latest && (
              <button className="btn" onClick={onAskAnother}>
                Hỏi câu khác
              </button>
            )}
          </div>
        </div>
      )}
      {view.state === "declined" && (
        <div className="warn" style={{ fontSize: 16 }}>
          {view.text}
        </div>
      )}
      {view.state === "needs_clarification" && (
        // Hỏi lại: the senses of an ambiguous term, each sent as the clarified question when tapped.
        <div className="card stack">
          <p style={{ fontSize: 16 }}>{view.text}</p>
          {view.messageId !== null &&
            view.clarifyOptions.map((o) => (
              <button
                key={o.term}
                className="btn block"
                style={{ justifyContent: "flex-start" }}
                disabled={busy || !latest}
                onClick={() => onClarify(o.query, view.messageId!)}
              >
                {o.label_vi}
              </button>
            ))}
        </div>
      )}
      {view.suggestions.length > 0 && !quiz && (
        <SuggestionBox suggestions={view.suggestions} />
      )}
    </>
  );
}

// "Đang tìm câu trả lời": the stages of this answer as they run, with the server's own labels.
function WorkBox({ view }: { view: TurnView }) {
  return (
    <div className="card stack" style={{ gap: 8 }} aria-live="polite">
      <p className="h2">Đang tìm câu trả lời</p>
      {view.steps.length === 0 && (
        <span className="spinner" role="status" aria-label="Đang bắt đầu" />
      )}
      <ul className="steps-list">
        {view.steps.map((s) => (
          <li key={s.id} className="row" style={{ gap: 10 }}>
            {s.status === "running" ? (
              <span className="spinner" />
            ) : (
              <span style={{ color: "var(--primary-dark)", display: "flex" }}>
                <Icon name="check" size={18} />
              </span>
            )}
            <span className={s.status === "running" ? "" : "muted"}>
              {s.label_vi}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// The chip above an answer; it opens the list of the steps that ran.
function TraceChip({ view }: { view: TurnView }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div>
      <button
        className="trace-chip"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
      >
        <span style={{ color: "var(--primary-dark)", display: "flex" }}>
          <Icon name="check" size={18} />
        </span>
        {view.summary ? chipLabel(view) : "Xem quá trình trả lời"}
        <Icon name={open ? "up" : "down"} size={16} />
      </button>
      <ul
        id={id}
        hidden={!open}
        className="steps-list"
        style={{ margin: "8px 0 0 8px" }}
      >
        {view.steps.map((s) => (
          <li key={s.id} className="muted small">
            {s.label_vi}
          </li>
        ))}
      </ul>
    </div>
  );
}

// "Hữu ích": the learner's verdict on this answer, kept with it.
function Helpful({
  messageId,
  initial,
}: {
  messageId: number;
  initial: boolean | null;
}) {
  const [helpful, setHelpful] = useState(initial === true);
  const [busy, setBusy] = useState(false);
  const rate = async () => {
    if (helpful || busy) return;
    setBusy(true);
    try {
      await api.post(`/messages/${messageId}/rating`, { helpful: true });
      setHelpful(true);
    } catch {
      // nothing changed: the button stays as it was and can be tapped again
    } finally {
      setBusy(false);
    }
  };
  return (
    <button
      className="icon-btn"
      aria-label="Hữu ích"
      aria-pressed={helpful}
      onClick={rate}
      style={{ color: helpful ? "var(--primary-dark)" : "var(--text-2)" }}
    >
      <Icon name="thumb" />
    </button>
  );
}

// Suggestions from the learner's own record (rules, not the model). Nothing happens until a tap.
export function SuggestionBox({
  suggestions,
  practiseLabel,
}: {
  suggestions: ChatSuggestion[];
  practiseLabel?: string;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState<Record<number, string>>({});
  const [error, setError] = useState<string>();

  const accept = async (s: ChatSuggestion) => {
    if (busy || added[s.id]) return;
    setBusy(true);
    setError(undefined);
    try {
      const done = await api.post<SuggestionAccepted>(
        `/chat/suggestions/${s.id}/accept`,
      );
      if (done.practice_set_id !== null)
        navigate(`/luyen-tap/bo-cau/${done.practice_set_id}`);
      else if (done.for_date) setAdded({ ...added, [s.id]: done.for_date });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="suggest-box stack" aria-label="Đề xuất từ gia sư">
      <p className="row" style={{ alignItems: "flex-start", gap: 8 }}>
        <AiStar size={18} />
        {suggestions[0].reason_vi}
      </p>
      {suggestions.map((s) =>
        s.kind === "practise" ? (
          <button
            key={s.id}
            className="btn primary"
            onClick={() => accept(s)}
            disabled={busy}
          >
            {practiseLabel ?? s.label_vi}
          </button>
        ) : (
          <button
            key={s.id}
            className="btn"
            onClick={() => accept(s)}
            disabled={busy || Boolean(added[s.id])}
          >
            {added[s.id]
              ? `Đã thêm vào phiên ngày ${dayMonth(added[s.id])}`
              : s.label_vi}
          </button>
        ),
      )}
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

// Under an answer in a chat opened from a quiz item.
function QuizActions({
  back,
  suggestions,
}: {
  back: string;
  suggestions: ChatSuggestion[];
}) {
  const navigate = useNavigate();
  const practise = suggestions.filter((s) => s.kind === "practise");
  return (
    <div className="stack" style={{ gap: 8 }}>
      {practise.length > 0 && (
        <SuggestionBox
          suggestions={practise}
          practiseLabel="Làm câu tương tự"
        />
      )}
      <button className="btn" onClick={() => navigate(back)}>
        Quay lại bài luyện
      </button>
    </div>
  );
}
