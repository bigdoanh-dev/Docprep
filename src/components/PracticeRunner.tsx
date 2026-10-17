import { Icon } from "./Icon";
import { SaveQuestion } from "./SaveQuestion";
import { CircleHelp } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import {
  Navigate,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { nextPanel } from "../lib/adaptation";
import {
  ApiError,
  api,
  type AdaptationSummary,
  type PracticeFeedback,
  type PracticeSetView,
} from "../lib/api";
import { useLoad } from "../lib/hooks";
import { newKey } from "../lib/keys";
import { CitationChip, useSourceSheet } from "./Answer";
import { QuizOptions } from "./QuizOptions";
import { LoadError, Loading } from "./Status";

// A practice set, one item at a time (FR-LRN-12, 33): today's weak-spot set (`base` is
// /session/today/practice) or a set opened by id (/practice-sets/<id>). It opens at the first item
// not answered yet, so leaving and coming back resumes in place. A set that is already closed is
// reported to the caller with its stored summary; an open set is closed only by the learner, on
// the last item.
export function PracticeRunner({
  base,
  header,
  onDone,
  missingTo,
  contextLabel,
}: {
  base: string;
  header: (countLabel?: string) => ReactNode;
  onDone: (summary: AdaptationSummary) => void;
  missingTo?: string; // where to go when there is no such set (no practice today)
  contextLabel: string; // what the set is, for the tutor's "Đang hỏi về: Câu n · …"
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const asked = Number(params.get("cau")); // "?cau=n": back from the tutor, on item n
  const {
    data: set,
    error,
    reload,
    setData,
  } = useLoad(async () => {
    try {
      return await api.get<PracticeSetView>(base);
    } catch (e) {
      if (missingTo && e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  }, [base]);
  // the item shown; until the learner moves, the one the address names, else the first unanswered one
  const [index, setIndex] = useState<number | undefined>(
    Number.isInteger(asked) && asked > 0 ? asked - 1 : undefined,
  );
  const [picked, setPicked] = useState<string | null>(null);
  // The choice already sent for this item. If its reply was lost the server may still hold it, and a
  // retry is answered with what was stored: so the retry sends the same choice, and it cannot be changed.
  const [sent, setSent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string>();
  const [whyOpen, setWhyOpen] = useState(false);
  const source = useSourceSheet();
  const shownAt = useRef(0); // when this item appeared: the answer time sent with the answer
  const answerKey = useRef(""); // one key per item shown, so "Kiểm tra" tapped again is the same answer
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const firstOpen = set ? set.items.findIndex((i) => i.feedback === null) : -1;
  const at =
    index ?? (firstOpen === -1 ? (set ? set.items.length - 1 : 0) : firstOpen);
  const item = set?.items[at];

  useEffect(() => {
    shownAt.current = Date.now();
    answerKey.current = newKey();
    setPicked(null);
    setSent(null);
    setWhyOpen(false);
    setActionError(undefined);
  }, [item?.question_id]);

  // A set that was closed earlier: its stored summary, without asking anything again.
  const closed = set?.completed === true;
  useEffect(() => {
    if (!closed) return;
    let alive = true;
    api.post<AdaptationSummary>(`${base}/complete`).then(
      (summary) => alive && onDoneRef.current(summary),
      (e: Error) => alive && setActionError(e.message),
    );
    return () => {
      alive = false;
    };
  }, [closed, base]);

  const run = async (action: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setActionError(undefined);
    try {
      await action();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (error)
    return (
      <div className="screen">
        {header()}
        <div className="body">
          <LoadError message={error} onRetry={reload} />
        </div>
      </div>
    );
  if (set === null && missingTo) return <Navigate to={missingTo} replace />;
  if (!set || !item || closed) {
    return (
      <div className="screen">
        {header()}
        <div className="body">
          {actionError ? <LoadError message={actionError} /> : <Loading />}
        </div>
      </div>
    );
  }

  const feedback = item.feedback;
  const chosen = item.chosen ?? sent ?? picked;
  const last = at === set.items.length - 1;

  const check = () =>
    run(async () => {
      const answer = sent ?? picked;
      if (answer === null) return;
      setSent(answer);
      const result = await api.post<PracticeFeedback>(
        `${base}/responses`,
        {
          question_id: item.question_id,
          chosen: answer,
          time_ms: Date.now() - shownAt.current,
        },
        { idempotencyKey: answerKey.current },
      );
      setIndex(at); // stay on this item to read the feedback
      setData({
        ...set,
        answered: set.answered + 1,
        items: set.items.map((i) =>
          i.question_id === item.question_id
            ? { ...i, chosen: answer, feedback: result }
            : i,
        ),
      });
    });

  const complete = () =>
    run(async () =>
      onDone(await api.post<AdaptationSummary>(`${base}/complete`)),
    );

  const panel = feedback && nextPanel(feedback);
  const correctText =
    feedback && item.options.find((o) => o.key === feedback.correct_key)?.text;
  const rationale =
    feedback && !feedback.correct && item.chosen
      ? feedback.rationales[item.chosen]
      : undefined;

  return (
    <div className="screen">
      {header(`Câu ${at + 1}/${set.items.length}`)}
      <div className="body stack">
        <ol role="list" aria-label="Kết quả từng câu" className="dots">
          {set.items.map((i, n) => {
            const state = i.feedback
              ? i.feedback.correct
                ? "right"
                : "wrong"
              : n === at
                ? "current"
                : "todo";
            const text = {
              right: "đúng",
              wrong: "sai",
              current: "đang làm",
              todo: "chưa làm",
            }[state];
            return (
              <li key={i.question_id} className={state}>
                <span>{n + 1}</span>
                <span className="sr">: {text}</span>
              </li>
            );
          })}
        </ol>
        <div className="quiz-question-meta">
          <div className="quiz-meta-left">
            <span className="quiz-type-badge">Trắc nghiệm kiến thức</span>
            <button
              className={`chip why-chip ${whyOpen ? "active" : ""}`}
              aria-expanded={whyOpen}
              aria-controls="item-reason"
              onClick={() => setWhyOpen(!whyOpen)}
            >
              <CircleHelp size={14} />
              Vì sao câu này?
            </button>
          </div>
          <SaveQuestion
            id={item.question_id}
            title={item.stem}
            detail={feedback?.explanation}
          />
        </div>
        {whyOpen && (
          <div id="item-reason" className="quiz-reason-box">
            <CircleHelp size={16} />
            <p>{item.reason_vi}</p>
          </div>
        )}
        <div className="quiz-stem-wrapper">
          <h2 className="title quiz-stem-title">
            {item.stem}
          </h2>
        </div>
        <QuizOptions
          options={item.options}
          picked={chosen}
          correctKey={feedback?.correct_key ?? null}
          disabled={busy || sent !== null}
          onPick={setPicked}
        />

        {feedback && (
          <div className="card stack" aria-live="polite">
            <p
              className="h2"
              style={{
                fontSize: 17,
                color: feedback.correct
                  ? "var(--primary-dark)"
                  : "var(--learning-dark)",
              }}
            >
              {feedback.correct ? (
                <>
                  <Icon name="check" size={18} /> Đúng
                </>
              ) : (
                <>
                  <Icon name="close" size={18} /> Chưa đúng — đáp án là{" "}
                  {correctText}
                </>
              )}
            </p>
            <p className="label">Giải thích của chuyên gia</p>
            <p style={{ fontSize: 16, color: "var(--text-2)" }}>
              {feedback.explanation}
            </p>
            {rationale && <p className="note">{rationale}</p>}
            <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
              <button
                className="btn"
                onClick={() =>
                  navigate(`/hoi-dap/tu-cau-hoi/${item.question_id}`, {
                    state: {
                      label: `Câu ${at + 1} · ${contextLabel}`,
                      stem: item.stem,
                      chosen:
                        item.options.find((o) => o.key === item.chosen)?.text ??
                        null,
                      correct: feedback.correct,
                      back: `${location.pathname}?cau=${at + 1}`,
                    },
                  })
                }
              >
                Hỏi gia sư về câu này
              </button>
              {feedback.citations.map((c) => (
                <CitationChip
                  key={c.passage_id}
                  citation={c}
                  onOpen={source.show}
                  label={c.page ? `tr. ${c.page}` : (c.article ?? "Nguồn")}
                />
              ))}
            </div>
          </div>
        )}
        {feedback?.remediation && (
          <div className="card stack">
            <p className="note">{feedback.remediation.reason}</p>
            <p className="label learning">Ví dụ</p>
            <h3 className="h2">{feedback.remediation.title}</h3>
            <div className="md">
              <ReactMarkdown>{feedback.remediation.body}</ReactMarkdown>
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
              {feedback.remediation.citations.map((c) => (
                <CitationChip
                  key={c.passage_id}
                  citation={c}
                  onOpen={source.show}
                  label={c.page ? `tr. ${c.page}` : (c.article ?? "Nguồn")}
                />
              ))}
            </div>
          </div>
        )}
        {panel && (
          <div className="dark-panel">
            <p className="h2">{panel.title}</p>
            {panel.note && <p className="muted small">{panel.note}</p>}
          </div>
        )}
        {actionError && (
          <p className="warn" role="alert">
            {actionError}
          </p>
        )}
      </div>

      <footer className="footer">
        {!feedback && (
          <button
            className="btn primary lg grow"
            onClick={check}
            disabled={busy || (sent ?? picked) === null}
          >
            Kiểm tra
          </button>
        )}
        {feedback && !last && (
          <button
            className="btn primary lg grow"
            onClick={() => setIndex(at + 1)}
            disabled={busy}
          >
            Câu tiếp
          </button>
        )}
        {feedback && last && (
          <button
            className="btn primary lg grow"
            onClick={complete}
            disabled={busy}
          >
            Hoàn thành bài luyện
          </button>
        )}
      </footer>

      {source.sheet}
    </div>
  );
}
