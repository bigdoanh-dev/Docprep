import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Sheet } from "../../components/Sheet";
import { LoadError, Loading } from "../../components/Status";
import { ApiError, api, type AttemptView, type Results } from "../../lib/api";
import { mmss } from "../../lib/format";

type Saved = { chosen: string | null; flagged: boolean };
type SaveState = "saved" | "saving" | "failed";

const LETTERS = ["A", "B", "C", "D", "E", "F"];

// Taking a mock exam: no navigation, one server-side countdown, autosave after every answer,
// resume in place after a reload or a dropped connection, auto-submit at time-up.
export function Exam() {
  const { attemptId } = useParams();
  const navigate = useNavigate();
  const [view, setView] = useState<AttemptView>();
  const [loadError, setLoadError] = useState<string>();
  const [answers, setAnswers] = useState<Record<string, Saved>>({});
  const [index, setIndex] = useState(0);
  const [remaining, setRemaining] = useState<number>();
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [navOpen, setNavOpen] = useState(false);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string>();
  const [timeUp, setTimeUp] = useState(false);
  const deadline = useRef(0); // local clock time at which the server deadline falls
  const pending = useRef(new Map<string, Saved>()); // answers not yet confirmed by the server
  const flushing = useRef<Promise<void> | null>(null);
  const resultsPath = `/thi-thu/ket-qua/${attemptId}`;

  const sync = useCallback(async () => {
    const fresh = await api.get<AttemptView>(`/attempts/${attemptId}`);
    deadline.current = Date.now() + fresh.remaining_s * 1000;
    return fresh;
  }, [attemptId]);

  useEffect(() => {
    sync().then(
      (fresh) => {
        if (fresh.submitted) return navigate(resultsPath, { replace: true });
        setView(fresh);
        setAnswers(fresh.answers);
        setRemaining(fresh.remaining_s);
      },
      (e: Error) => setLoadError(e.message),
    );
  }, [sync, navigate, resultsPath]);

  const flush = useCallback(async () => {
    if (flushing.current) return flushing.current;
    const run = async () => {
      if (pending.current.size === 0) return;
      setSaveState("saving");
      while (pending.current.size > 0) {
        const [questionId, saved] = pending.current.entries().next().value!;
        try {
          await api.put(`/attempts/${attemptId}/answers/${questionId}`, saved);
          if (pending.current.get(questionId) === saved)
            pending.current.delete(questionId);
        } catch (e) {
          if (e instanceof ApiError && e.code === "attempt_closed") {
            pending.current.clear();
            setTimeUp(true);
            return;
          }
          setSaveState("failed");
          return;
        }
      }
      setSaveState("saved");
    };
    flushing.current = run().finally(() => {
      flushing.current = null;
    });
    return flushing.current;
  }, [attemptId]);

  // Countdown from the server deadline, a resync every 30 s, and retry of unsaved answers.
  useEffect(() => {
    if (!view || timeUp) return;
    const timer = window.setInterval(() => {
      const left = Math.max(
        0,
        Math.ceil((deadline.current - Date.now()) / 1000),
      );
      setRemaining(left);
      if (left === 0) {
        setTimeUp(true);
        sync().catch(() => undefined); // the server auto-submits when it sees the passed deadline
      } else if (left % 30 === 0) {
        sync()
          .then((fresh) => fresh.submitted && setTimeUp(true))
          .catch(() => undefined);
      } else if (left % 5 === 0 && pending.current.size > 0) {
        flush();
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [view, timeUp, sync, flush]);

  const save = (questionId: string, next: Saved) => {
    setAnswers((all) => ({ ...all, [questionId]: next }));
    pending.current.set(questionId, next);
    flush();
  };

  const submit = async () => {
    setSubmitting(true);
    setSubmitError(undefined);
    try {
      await flush();
      if (pending.current.size > 0)
        throw new Error(
          "Còn câu trả lời chưa lưu được. Hãy kết nối lại và thử nộp bài sau.",
        );
      await api.post<Results>(`/attempts/${attemptId}/submit`);
      navigate(resultsPath, { replace: true });
    } catch (e) {
      setSubmitError((e as Error).message);
      setSubmitting(false);
    }
  };

  if (loadError)
    return (
      <div className="screen">
        <div className="body">
          <LoadError message={loadError} />
        </div>
      </div>
    );
  if (!view || remaining === undefined)
    return (
      <div className="screen">
        <div className="body">
          <Loading />
        </div>
      </div>
    );

  const total = view.questions.length;
  const question = view.questions[index];
  const current = answers[question.id] ?? { chosen: null, flagged: false };
  const answered = view.questions.filter(
    (q) => answers[q.id]?.chosen != null,
  ).length;
  const flagged = view.questions.filter((q) => answers[q.id]?.flagged).length;
  const warn = remaining <= view.warning_s;

  return (
    <div className="screen">
      <header
        className="topbar"
        style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}
      >
        <div className="row">
          <div className="grow">
            <h1 style={{ fontSize: 16 }}>{view.title}</h1>
            <div className="small muted" role="status">
              {saveState === "saved" ? (
                <span>
                  <Icon name="check" size={14} /> Đã lưu
                </span>
              ) : saveState === "saving" ? (
                "Đang lưu…"
              ) : (
                "Chưa lưu được, đang thử lại…"
              )}
            </div>
          </div>
          <div
            role="timer"
            aria-label={`Thời gian còn lại ${mmss(remaining)}`}
            style={{
              fontSize: 18,
              fontWeight: 700,
              fontVariantNumeric: "tabular-nums",
              borderRadius: 10,
              padding: "6px 12px",
              color: "#fff",
              background: warn ? "var(--learning)" : "var(--ink)",
            }}
          >
            {mmss(remaining)}
          </div>
          <button
            className="btn outline-primary"
            onClick={() => setSubmitOpen(true)}
            style={{ minHeight: 44, padding: "0 14px" }}
          >
            Nộp bài
          </button>
        </div>
        <div
          className="progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={answered}
          aria-label="Số câu đã trả lời"
        >
          <span style={{ width: `${(answered / total) * 100}%` }} />
        </div>
      </header>

      <div className="body stack">
        {warn && (
          <p className="warn" role="alert">
            Còn dưới {Math.round(view.warning_s / 60)} phút. Bài vẫn tự lưu.
          </p>
        )}
        <div className="row">
          <span className="grow h2 muted">
            Câu {question.n} / {total}
          </span>
          <button
            className="btn"
            aria-pressed={current.flagged}
            disabled={submitting || timeUp}
            onClick={() =>
              save(question.id, { ...current, flagged: !current.flagged })
            }
            style={{
              minHeight: 44,
              padding: "0 12px",
              fontSize: 13,
              ...(current.flagged
                ? {
                    borderColor: "var(--learning)",
                    background: "var(--learning-tint)",
                    color: "var(--learning-dark)",
                  }
                : {}),
            }}
          >
            <Icon name="flag" size={18} />
            {current.flagged ? "Đã đánh dấu" : "Đánh dấu"}
          </button>
        </div>
        <h2 className="title" style={{ fontSize: 19 }}>
          {question.stem}
        </h2>
        <div
          role="radiogroup"
          aria-label="Các phương án"
          className="stack"
          style={{ gap: 10 }}
        >
          {question.options.map((o, i) => {
            const on = current.chosen === o.key;
            return (
              <button
                key={o.key}
                role="radio"
                aria-checked={on}
                disabled={submitting || timeUp}
                onClick={() => save(question.id, { ...current, chosen: o.key })}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  width: "100%",
                  minHeight: 56,
                  padding: "10px 14px",
                  borderRadius: 14,
                  textAlign: "left",
                  lineHeight: 1.4,
                  color: "var(--ink)",
                  background: on ? "var(--primary-tint)" : "var(--surface)",
                  border: on
                    ? "2px solid var(--primary)"
                    : "1px solid var(--border-input)",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: 30,
                    height: 30,
                    flexShrink: 0,
                    borderRadius: 15,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 13,
                    fontWeight: 600,
                    background: on ? "var(--primary)" : "var(--soft)",
                    color: on ? "#fff" : "var(--ink)",
                  }}
                >
                  {LETTERS[i]}
                </span>
                {o.text}
              </button>
            );
          })}
        </div>
      </div>

      <footer className="footer">
        <button
          className="btn grow"
          onClick={() => setIndex(index - 1)}
          disabled={index === 0}
        >
          Câu trước
        </button>
        <button className="btn soft grow" onClick={() => setNavOpen(true)}>
          Danh sách
        </button>
        <button
          className="btn primary grow"
          onClick={() => setIndex(index + 1)}
          disabled={index === total - 1}
        >
          Câu sau
        </button>
      </footer>

      <Sheet
        open={navOpen}
        onClose={() => setNavOpen(false)}
        title="Danh sách câu hỏi"
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 10,
          }}
        >
          {view.questions.map((q, i) => {
            const a = answers[q.id];
            const done = a?.chosen != null;
            return (
              <button
                key={q.id}
                onClick={() => {
                  setIndex(i);
                  setNavOpen(false);
                }}
                aria-label={`Câu ${q.n}, ${done ? "đã trả lời" : "chưa trả lời"}${a?.flagged ? ", đã đánh dấu" : ""}`}
                aria-current={i === index}
                style={{
                  height: 44,
                  borderRadius: 10,
                  fontSize: 14,
                  background: done ? "var(--primary)" : "var(--surface)",
                  color: done ? "#fff" : "var(--ink)",
                  border: a?.flagged
                    ? "2px solid var(--learning)"
                    : done
                      ? 0
                      : "1px solid #8a938f",
                  outline: i === index ? "2px solid var(--ink)" : undefined,
                  outlineOffset: 2,
                }}
              >
                {q.n}
              </button>
            );
          })}
        </div>
        <p className="muted small" style={{ marginTop: 14 }}>
          Ô xanh: đã trả lời · viền cam: đánh dấu · ô trắng: chưa trả lời
        </p>
      </Sheet>

      <Sheet
        open={submitOpen}
        onClose={() => !submitting && setSubmitOpen(false)}
        title="Nộp bài?"
      >
        <div className="stack">
          <p style={{ fontSize: 16 }}>
            {total - answered} câu chưa trả lời · {flagged} câu đánh dấu
          </p>
          {submitError && (
            <p className="warn" role="alert">
              {submitError}
            </p>
          )}
          <div className="row">
            <button
              className="btn grow"
              onClick={() => setSubmitOpen(false)}
              disabled={submitting}
            >
              Làm tiếp
            </button>
            <button
              className="btn primary grow"
              onClick={submit}
              disabled={submitting}
            >
              {submitting ? "Đang nộp…" : "Nộp bài"}
            </button>
          </div>
        </div>
      </Sheet>

      {timeUp && (
        <div className="scrim" style={{ alignItems: "center", padding: 24 }}>
          <div
            className="card stack center"
            role="alertdialog"
            aria-label="Hết giờ"
            style={{ width: "100%" }}
          >
            <h2 className="title">Hết giờ</h2>
            <p>Bài đã được nộp tự động.</p>
            <p className="muted">
              Bạn trả lời {answered}/{total} câu.
            </p>
            <button
              className="btn primary lg block"
              autoFocus
              onClick={() => navigate(resultsPath, { replace: true })}
            >
              Xem kết quả
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
