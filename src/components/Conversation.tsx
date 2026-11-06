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
import { postSSE, activeSessionTurn, resumeTurn, cancelTurn } from "../lib/sse";
import { useSourceSheet } from "./Answer";
import { AssistantTurn, type QuizContext } from "./ChatTurn";
import { ArrowUp, ArrowUpRight, BookOpenText, History } from "lucide-react";
import { formatDate } from "../lib/format";

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
  starterLabels,
  autoSend,
  resume,
  onResume,
  intro,
  quiz,
}: {
  sessionId: number | null;
  onSession?: (id: number) => void;
  questionId?: string;
  starters: string[];
  starterLabels?: string[]; // the kind of question each starter is, shown above it
  autoSend?: string; // a new conversation that starts with this question at once
  resume?: { id: number; title: string; updated_at: string }; // offered on the welcome screen
  onResume?: (id: number) => void;
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
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  // The conversation whose turns are on screen. Each time another one is shown the generation moves
  // on: an answer still arriving for the previous one is dropped from the screen (it is stored all
  // the same), and the turns are new components, so nothing opened or pressed carries over.
  const shown = useRef<number | null>(null);
  const generationRef = useRef(0);
  const [generation, setGeneration] = useState(0);
  const source = useSourceSheet();
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setCurrent(sessionId);
    setActiveTurnId(null);
    setDraft("");
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
    let recovering = false;
    const controller = new AbortController();
    api
      .get<ChatMessageList>(`/chat/sessions/${sessionId}/messages?limit=100`)
      .then(
        async ({ items, next_cursor }) => {
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
          try {
            const active = await activeSessionTurn(sessionId);
            if (!alive || !active) return;
            recovering = true;
            setBusy(true);
            setActiveTurnId(active.turn_id);
            setTurns((all) => [...all, { role: "assistant", view: startTurn() }]);
            await resumeTurn(active.turn_id, (event, data) => {
              if (!alive) return;
              setTurns((all) => all.map((turn, i) => i === all.length - 1 && turn.role === "assistant"
                ? { ...turn, view: applyEvent(turn.view, event, data) } : turn));
            }, controller.signal);
          } catch (error) {
            if (alive && recovering) setTurns((all) => all.map((turn, i) => i === all.length - 1 && turn.role === "assistant"
              ? { ...turn, view: failTurn(turn.view, (error as Error).message) } : turn));
          } finally {
            if (alive) { setBusy(false); setActiveTurnId(null); }
          }
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
      controller.abort();
    };
  }, [sessionId, historyReload]);

  useEffect(() => {
    const area = scrollRef.current;
    if (
      turns.length > 0 &&
      area &&
      area.getClientRects().length &&
      followLatest.current
    )
      area.scrollTop = area.scrollHeight;
  }, [turns]);

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "24px";
    input.style.height = `${Math.min(Math.max(24, input.scrollHeight), 120)}px`;
  }, [draft]);

  // The last answer is a quiz question: what is typed next is the learner's answer to it.
  const lastTurn = turns[turns.length - 1];
  const awaitingAnswer =
    lastTurn?.role === "assistant" &&
    lastTurn.view.phase === "done" &&
    lastTurn.view.mode === "kiem_tra";
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
  // `mode`: a supported tutor move sent to Phase 1; the server owns its evidence and history.
  const send = async (
    text: string,
    detail = false,
    clarifies?: number,
    mode?: string,
  ) => {
    if (busy || historyLoading || historyCursor || historyError || !text.trim())
      return;
    const generationAtSend = generationRef.current;
    const update = updateFor(generationAtSend);
    followLatest.current = true;
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
      const body = {
        text: text.trim(),
        detail,
        ...(clarifies === undefined ? {} : { clarifies_message_id: clarifies }),
        ...(mode ? { mode } : {}),
      };
      await postSSE(`/chat/sessions/${id}/messages`, body, (event, data) => {
        if (data.turn_id && generationRef.current === generationAtSend) setActiveTurnId(data.turn_id);
        update((view) => applyEvent(view, event, data));
        if (event === "final") ended = true;
      });
      if (!ended) throw new Error(NO_ANSWER);
    } catch (e) {
      update((view) => failTurn(view, (e as Error).message || NO_ANSWER));
    } finally {
      if (generationRef.current === generationAtSend) { setBusy(false); setActiveTurnId(null); }
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
  // Asked once, when a new conversation is opened with a question from another screen.
  const autoSent = useRef(false);
  useEffect(() => {
    let active = true;
    // StrictMode replays mount effects in Vite. Dispatch only after its cleanup,
    // otherwise the first send belongs to a discarded conversation generation.
    queueMicrotask(() => {
      if (!active || !autoSend || autoSent.current || sessionId !== null || historyLoading || historyCursor || historyError) return;
      autoSent.current = true;
      void send(autoSend);
    });
    return () => { active = false; };
  }, [autoSend, sessionId, historyLoading, historyCursor, historyError]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(draft);
  };

  return (
    <>
      <div
        className="body tutor-messages"
        ref={scrollRef}
        aria-live="polite"
        onScroll={(e) => {
          const el = e.currentTarget;
          followLatest.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 100;
        }}
      >
        {intro}
        {historyLoading && (
          <p className="tutor-loading" role="status">
            Đang mở cuộc trò chuyện…
          </p>
        )}
        {turns.length === 0 && !historyLoading && !historyError && (
          <div className="tutor-welcome">
            {!quiz && (
              <div className="tutor-welcome-intro">
                <div className="tutor-welcome-mark">
                  <BookOpenText size={28} strokeWidth={1.5} />
                </div>
                <h2>Bạn muốn hiểu rõ điều gì hôm nay?</h2>
                <p>Cùng làm rõ kiến thức, từng câu hỏi một.</p>
              </div>
            )}
            {resume && !quiz && (
              <button
                className="tutor-resume"
                onClick={() => onResume?.(resume.id)}
                disabled={busy}
              >
                <History size={18} aria-hidden="true" />
                <span>
                  <small>
                    Tiếp tục cuộc trò chuyện · {formatDate(resume.updated_at)}
                  </small>
                  <strong>{resume.title}</strong>
                </span>
                <ArrowUpRight size={16} />
              </button>
            )}
            <div className="tutor-starters">
              {starters.map((q, i) => (
                <button key={q} onClick={() => send(q)} disabled={busy}>
                  <span>
                    <small>
                      {quiz
                        ? "Tìm hiểu thêm"
                        : (starterLabels ?? [
                            "So sánh khái niệm",
                            "Làm rõ kiến thức",
                            "Giải thích ý nghĩa",
                          ])[i % (starterLabels?.length ?? 3)]}
                    </small>
                    <strong>{q}</strong>
                  </span>
                  <ArrowUpRight size={16} />
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="stack tutor-turns">
          {turns.map((turn, i) =>
            turn.role === "user" ? (
              <div key={`${generation}-${i}`} className="tutor-user-message">
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
                onMove={(text, mode) => send(text, false, undefined, mode)}
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

      {busy && activeTurnId && <button type="button" onClick={() => {
        void cancelTurn(activeTurnId).catch((error: Error) => setHistoryError(error.message));
      }}>Hủy lượt AI</button>}
      <form className="footer tutor-composer" onSubmit={onSubmit}>
        <div className="tutor-composer-box">
          <textarea
            ref={inputRef}
            rows={1}
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
            }}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing &&
                window.matchMedia("(pointer: fine)").matches
              ) {
                e.preventDefault();
                send(draft);
              }
            }}
            disabled={
              busy || historyLoading || !!historyCursor || !!historyError
            }
            placeholder={
              awaitingAnswer
                ? "Nhập câu trả lời của bạn…"
                : "Hỏi gia sư về bài học…"
            }
            aria-label="Câu hỏi của bạn"
          />
          <div className="tutor-composer-bottom">
            <button
              type="submit"
              disabled={
                busy ||
                historyLoading ||
                !!historyCursor ||
                !!historyError ||
                !draft.trim()
              }
              aria-label="Gửi câu hỏi"
            >
              <ArrowUp size={18} />
            </button>
          </div>
        </div>
        <p className="tutor-footnote">
          AI có thể sai. Hãy đối chiếu nguồn học liệu.
        </p>
      </form>
      {source.sheet}
    </>
  );
}
