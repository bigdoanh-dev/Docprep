import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  api,
  type ChatMessageList,
  type ExamForm,
  type Listed,
} from "../lib/api";
import {
  applyEvent,
  failTurn,
  fromStored,
  startTurn,
  type TurnView,
} from "../lib/chatTurn";
import { postSSE } from "../lib/sse";
import { useSourceSheet } from "./Answer";
import { AssistantTurn, type QuizContext } from "./ChatTurn";
import { Icon } from "./Icon";

type Turn =
  { role: "user"; text: string } | { role: "assistant"; view: TurnView };

const FOLLOW_UP = "Giải thích thêm";
const NO_ANSWER = "Không nhận được câu trả lời. Vui lòng thử lại.";

// A conversation of Hỏi đáp: its turns, the answer stream, and the composer. Used by the chat tab and
// by the chat opened from a quiz item. `sessionId` is the conversation to show (null: a new one);
// `onSession` is told the id of a conversation this component started.
export function Conversation({
  sessionId,
  onSession,
  questionId,
  starters,
  intro,
  quiz,
}: {
  sessionId: number | null;
  onSession?: (id: number) => void;
  questionId?: string;
  starters: string[];
  intro?: ReactNode;
  quiz?: QuizContext;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [historyCursor, setHistoryCursor] = useState<string | null>(null),
    [historyBusy, setHistoryBusy] = useState(false),
    [historyError, setHistoryError] = useState("");
  const [historyLoading, setHistoryLoading] = useState(sessionId !== null),
    [historyReload, setHistoryReload] = useState(0);
  const [current, setCurrent] = useState<number | null>(sessionId);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  // The conversation whose turns are on screen. Each time another one is shown the generation moves
  // on: an answer still arriving for the previous one is dropped from the screen (it is stored all
  // the same), and the turns are new components, so nothing opened or pressed carries over.
  const shown = useRef<number | null>(null);
  const generationRef = useRef(0);
  const [generation, setGeneration] = useState(0);
  const source = useSourceSheet();
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setCurrent(sessionId);
    if (sessionId !== null && sessionId === shown.current) return; // its turns are already here
    // `shown` is set only once the turns are really here (loaded, or started on this screen): set
    // earlier, an effect run twice on mount would skip the load it had just begun.
    shown.current = null;
    generationRef.current += 1;
    setGeneration(generationRef.current);
    setBusy(false);
    setTurns([]);
    setHistoryCursor(null);
    setHistoryError("");
    setHistoryBusy(false);
    setHistoryLoading(sessionId !== null);
    if (sessionId === null) return;
    let alive = true;
    api
      .get<ChatMessageList>(`/chat/sessions/${sessionId}/messages?limit=100`)
      .then(
        ({ items, next_cursor }) => {
          if (!alive) return;
          setHistoryLoading(false);
          shown.current = sessionId;
          setHistoryCursor(next_cursor ?? null);
          setTurns(
            items.map((m): Turn =>
              m.role === "user"
                ? { role: "user", text: m.text }
                : { role: "assistant", view: fromStored(m) },
            ),
          );
        },
        (e: Error) => {
          if (alive) {
            setHistoryError(e.message);
            setHistoryLoading(false);
          }
        },
      );
    return () => {
      alive = false;
    };
  }, [sessionId, historyReload]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns]);

  const lastQuestion = [...turns]
    .reverse()
    .find((t) => t.role === "user" && t.text !== FOLLOW_UP) as
    { role: "user"; text: string } | undefined;
  // Changes the turn being answered, as long as its conversation is still the one shown.
  const updateFor =
    (generationAtSend: number) => (change: (view: TurnView) => TurnView) => {
      if (generationRef.current !== generationAtSend) return;
      setTurns((all) =>
        all.map((t, i) =>
          i === all.length - 1 && t.role === "assistant"
            ? { ...t, view: change(t.view) }
            : t,
        ),
      );
    };

  // `clarifies`: the id of the answer that asked back, when this message is the learner's choice of a sense.
  const send = async (text: string, detail = false, clarifies?: number) => {
    if (busy || historyLoading || historyCursor || historyError || !text.trim())
      return;
    const generationAtSend = generationRef.current;
    const update = updateFor(generationAtSend);
    setBusy(true);
    setDraft("");
    setTurns((all) => [
      ...all,
      { role: "user", text: detail ? FOLLOW_UP : text.trim() },
      { role: "assistant", view: startTurn() },
    ]);
    try {
      const exams = await api.get<Listed<ExamForm>>("/exams");
      if (
        exams.items.some(
          (f) => f.open_attempt_id !== null && (f.open_remaining_s ?? 0) > 0,
        )
      )
        throw new Error(
          "Không mở tutor khi đang có bài thi chưa nộp. Hãy hoàn thành bài thi trước.",
        );
      let id = current;
      if (id === null) {
        id = (
          await api.post<{ id: number }>(
            "/chat/sessions",
            questionId ? { question_id: questionId } : {},
          )
        ).id;
        if (generationRef.current === generationAtSend) {
          shown.current = id;
          setCurrent(id);
          onSession?.(id);
        }
      }
      let ended = false;
      const body =
        clarifies === undefined
          ? { text: text.trim(), detail }
          : { text: text.trim(), detail, clarifies_message_id: clarifies };
      await postSSE(`/chat/sessions/${id}/messages`, body, (event, data) => {
        update((view) => applyEvent(view, event, data));
        if (event === "final") ended = true;
      });
      if (!ended) throw new Error(NO_ANSWER);
    } catch (e) {
      update((view) => failTurn(view, (e as Error).message || NO_ANSWER));
    } finally {
      if (generationRef.current === generationAtSend) setBusy(false);
    }
  };

  const loadMoreHistory = async () => {
    if (!historyCursor || sessionId === null || historyBusy) return;
    const gen = generationRef.current;
    setHistoryBusy(true);
    setHistoryError("");
    try {
      const page = await api.get<ChatMessageList>(
        `/chat/sessions/${sessionId}/messages?limit=100&cursor=${encodeURIComponent(historyCursor)}`,
      );
      if (gen !== generationRef.current) return;
      setTurns((prev) => [
        ...prev,
        ...page.items.map((m): Turn =>
          m.role === "user"
            ? { role: "user", text: m.text }
            : { role: "assistant", view: fromStored(m) },
        ),
      ]);
      setHistoryCursor(page.next_cursor ?? null);
    } catch (e) {
      if (gen === generationRef.current) setHistoryError((e as Error).message);
    } finally {
      if (gen === generationRef.current) setHistoryBusy(false);
    }
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(draft);
  };

  return (
    <>
      <div className="body" aria-live="polite">
        {intro}
        {turns.length === 0 && (
          <div className="stack" style={{ marginTop: 16 }}>
            {!quiz && (
              <p className="muted">
                Hỏi về nội dung ôn thi. Mở nguồn trong câu trả lời để đối chiếu
                với học liệu.
              </p>
            )}
            {starters.map((q) => (
              <button
                key={q}
                className="btn block"
                style={{
                  justifyContent: "flex-start",
                  textAlign: "left",
                  padding: "10px 14px",
                }}
                onClick={() => send(q)}
                disabled={busy}
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <div className="stack" style={{ marginTop: 12 }}>
          {turns.map((turn, i) =>
            turn.role === "user" ? (
              <div
                key={`${generation}-${i}`}
                style={{
                  alignSelf: "flex-end",
                  maxWidth: "85%",
                  background: "var(--primary)",
                  color: "#fff",
                  padding: "10px 14px",
                  borderRadius: "16px 16px 4px 16px",
                  fontSize: 16,
                }}
              >
                {turn.text}
              </div>
            ) : (
              <AssistantTurn
                key={`${generation}-${i}`}
                view={turn.view}
                latest={i === turns.length - 1}
                busy={busy}
                quiz={quiz}
                onCite={source.show}
                onExplainMore={() =>
                  lastQuestion && send(lastQuestion.text, true)
                }
                onAskAnother={() => inputRef.current?.focus()}
                onClarify={(query, messageId) => send(query, false, messageId)}
                onRetry={() => lastQuestion && send(lastQuestion.text)}
              />
            ),
          )}
        </div>
        {historyCursor && (
          <button
            className="btn"
            onClick={loadMoreHistory}
            disabled={historyBusy}
          >
            {historyBusy ? "Đang tải…" : "Tải tiếp hội thoại"}
          </button>
        )}
        {historyError && (
          <div>
            <p className="warn" role="alert">
              {historyError}
            </p>
            <button
              className="btn"
              onClick={() =>
                historyCursor
                  ? loadMoreHistory()
                  : setHistoryReload((v) => v + 1)
              }
            >
              Thử tải lại hội thoại
            </button>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="footer"
        onSubmit={onSubmit}
        style={{ alignItems: "center" }}
      >
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={busy || historyLoading || !!historyCursor || !!historyError}
          placeholder="Hỏi về nội dung ôn thi…"
          aria-label="Câu hỏi của bạn"
          className="grow"
          style={{
            minHeight: 48,
            padding: "0 16px",
            borderRadius: 999,
            border: "1px solid var(--border-input)",
            background: "var(--bg)",
          }}
        />
        <button
          type="submit"
          className="btn primary"
          disabled={
            busy ||
            historyLoading ||
            !!historyCursor ||
            !!historyError ||
            !draft.trim()
          }
          aria-label="Gửi"
          style={{ width: 48, padding: 0, borderRadius: 24 }}
        >
          <Icon name="arrow" />
        </button>
      </form>
      {source.sheet}
    </>
  );
}
