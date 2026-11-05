import { SaveQuestion } from "../../components/SaveQuestion";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Link,
  Navigate,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { CitationChip, useSourceSheet } from "../../components/Answer";
import { Icon } from "../../components/Icon";
import { QuizOptions } from "../../components/QuizOptions";
import { SessionHeader } from "../../components/SessionHeader";
import { LoadError, Loading } from "../../components/Status";
import { TutorSheet } from "../../components/TutorSheet";
import {
  api,
  type Feedback,
  type SessionToday,
  type UnitItem,
  type UnitView,
} from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { newKey } from "../../lib/keys";

// A unit, one item at a time (FR-LRN-32, 33). With `?phien=1` it is step 3 of Phiên hôm nay: the same
// unit under the session's header, ending on the session's last screen.
export function Unit() {
  const { unitId } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const asStep = params.get("phien") === "1";
  const {
    data: view,
    error,
    reload,
    setData,
  } = useLoad(() => api.get<UnitView>(`/units/${unitId}/next`), [unitId]);
  // The session, for the header and to know that this unit is today's step. The unit does not wait for it.
  const { data: session, error: sessionError } = useLoad(
    async () => (asStep ? api.get<SessionToday>("/session/today") : undefined),
    [asStep],
  );
  const sessionKnown = session !== undefined || sessionError !== undefined;
  // "?phien=1" is only a request: an address kept from another day, or of another unit, is an
  // ordinary unit. Only the unit that today's session continues with is shown as its step.
  const inSession =
    asStep &&
    (!sessionKnown ||
      session?.steps.find((s) => s.kind === "continue")?.unit_id === unitId);
  const [picked, setPicked] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string>();
  const [tutorOpen, setTutorOpen] = useState(false);
  const [hintOpen, setHintOpen] = useState(false);
  // The choice already sent for this item. If its reply was lost the server may still hold it, and a
  // retry is answered with what was stored: so the retry sends the same choice, and it cannot be changed.
  const [sent, setSent] = useState<string | null>(null);
  const source = useSourceSheet();

  const item = view?.item ?? null;
  const shownAt = useRef(0); // when this item appeared: the answer time sent with a quiz answer
  const answerKey = useRef(""); // one key per item shown, so "Kiểm tra" tapped again is the same answer

  // A reload on an answered quiz item restores its feedback instead of offering the question again.
  useEffect(() => {
    setPicked(item?.chosen ?? null);
    setFeedback(item?.feedback ?? null);
    setTutorOpen(false);
    setHintOpen(false);
    setActionError(undefined);
  }, [item?.unit_item_id, item?.chosen, item?.feedback]);

  useEffect(() => {
    shownAt.current = Date.now();
    answerKey.current = newKey();
    setSent(null);
  }, [item?.unit_item_id]);

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

  const check = () =>
    run(async () => {
      const chosen = sent ?? picked;
      if (!item || chosen === null) return;
      setSent(chosen);
      setFeedback(
        await api.post<Feedback>(
          `/units/${unitId}/responses`,
          {
            unit_item_id: item.unit_item_id,
            chosen,
            time_ms: Date.now() - shownAt.current,
          },
          { idempotencyKey: answerKey.current },
        ),
      );
    });

  const advance = () =>
    run(async () => {
      if (!item) return;
      setData(
        await api.post<UnitView>(`/units/${unitId}/advance`, {
          unit_item_id: item.unit_item_id,
        }),
      );
    });

  if (error)
    return (
      <div className="screen">
        <div className="body">
          <LoadError message={error} onRetry={reload} />
        </div>
      </div>
    );
  if (!view)
    return (
      <div className="screen">
        <div className="body">
          <Loading />
        </div>
      </div>
    );

  const isQuiz = item?.kind === "quiz";
  const answered = isQuiz && feedback !== null;

  return (
    <div className="screen">
      {inSession ? (
        <SessionHeader
          session={session}
          current="continue"
          countLabel={
            view.done
              ? undefined
              : `Mục ${Math.min(view.position + 1, view.total)}/${view.total}`
          }
        />
      ) : (
        <header
          className="topbar"
          style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}
        >
          <div className="row">
            <Link to="/luyen-tap" className="icon-btn" aria-label="Đóng chủ đề">
              <Icon name="close" />
            </Link>
            <h1>
              {view.topic}
              <div className="sub">Luyện tập</div>
            </h1>
          </div>
          <div
            className="row"
            style={{ gap: 6 }}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={view.total}
            aria-valuenow={view.position}
            aria-label="Tiến độ chủ đề"
          >
            {Array.from({ length: view.total }, (_, i) => (
              <span
                key={i}
                className="grow"
                style={{
                  height: 5,
                  borderRadius: 3,
                  background:
                    i < view.position
                      ? "var(--primary)"
                      : i === view.position
                        ? "var(--ink)"
                        : "var(--border)",
                }}
              />
            ))}
          </div>
        </header>
      )}

      <div className="body stack">
        {inSession && !view.done && <p className="muted small">{view.topic}</p>}
        {view.done && !inSession && <EndScreen cards={view.cards_created} />}
        {/* The session decides what comes after its step: its last screen, or a step still open. */}
        {view.done &&
          inSession &&
          (sessionKnown ? (
            <Navigate
              to="/phien"
              replace
              state={{
                note:
                  view.cards_created > 0
                    ? `Đã tạo ${view.cards_created} thẻ ôn từ câu sai`
                    : undefined,
              }}
            />
          ) : (
            <Loading />
          ))}
        {item && !isQuiz && <ContentItem item={item} onCite={source.show} />}
        {item && isQuiz && (
          <QuizItem
            item={item}
            picked={sent ?? picked}
            feedback={feedback}
            disabled={busy || sent !== null}
            onPick={setPicked}
            onCite={source.show}
            onExplain={() => setTutorOpen(true)}
          />
        )}
        {actionError && (
          <p className="warn" role="alert">
            {actionError}
          </p>
        )}
      </div>

      {item && (
        <footer className="footer">
          {answered && (
            <button
              className="icon-btn boxed"
              aria-label="Hỏi gia sư"
              onClick={() =>
                item.question &&
                navigate(`/hoi-dap/tu-cau-hoi/${item.question.id}`, {
                  state: {
                    label: `Kiểm tra nhanh · ${view.topic}`,
                    stem: item.question.stem,
                    chosen:
                      item.question.options.find((o) => o.key === picked)
                        ?.text ?? null,
                    correct: feedback?.correct ?? false,
                    back: `/luyen-tap/${unitId}${asStep ? "?phien=1" : ""}`,
                  },
                })
              }
            >
              <Icon name="chat" />
            </button>
          )}
          {isQuiz && !answered && (
            <>
              <button
                className="btn"
                onClick={() => setHintOpen(true)}
                disabled={busy}
              >
                Gợi ý
              </button>
              <button className="btn" onClick={advance} disabled={busy}>
                Bỏ qua
              </button>
            </>
          )}
          {isQuiz && !answered ? (
            <button
              className="btn primary lg grow"
              onClick={check}
              disabled={busy || picked === null}
            >
              Kiểm tra
            </button>
          ) : (
            <button
              className="btn primary lg grow"
              onClick={advance}
              disabled={busy}
            >
              Tiếp tục
            </button>
          )}
        </footer>
      )}

      {/* Two sheets, so the hint asked before the answer and the explanation asked after it keep their own text. */}
      {isQuiz && item.question && (
        <>
          <TutorSheet
            mode="hint"
            open={hintOpen && !answered}
            onClose={() => setHintOpen(false)}
            questionId={item.question.id}
            topic={view.topic}
            onCite={source.show}
            key={`${item.unit_item_id}-hint`}
          />
          <TutorSheet
            open={tutorOpen}
            onClose={() => setTutorOpen(false)}
            questionId={item.question.id}
            topic={view.topic}
            onCite={source.show}
            key={item.unit_item_id}
          />
        </>
      )}
      {source.sheet}
    </div>
  );
}

function ContentItem({
  item,
  onCite,
}: {
  item: UnitItem;
  onCite: (c: NonNullable<UnitItem["citations"]>[number]) => void;
}) {
  const remediation = item.kind === "remediation";
  return (
    <>
      {remediation && item.reason && <p className="note">{item.reason}</p>}
      <p className={`label ${remediation ? "learning" : "primary"}`}>
        {remediation ? "Ví dụ" : "Nội dung"}
      </p>
      <h2 className="title">{item.title}</h2>
      <div className="md">
        <ReactMarkdown>{item.body ?? ""}</ReactMarkdown>
      </div>
      <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
        {item.citations?.map((c) => (
          <CitationChip
            key={c.passage_id}
            citation={c}
            onOpen={onCite}
            label={c.page ? `tr. ${c.page}` : (c.article ?? "Nguồn")}
          />
        ))}
      </div>
    </>
  );
}

function QuizItem({
  item,
  picked,
  feedback,
  disabled,
  onPick,
  onCite,
  onExplain,
}: {
  item: UnitItem;
  picked: string | null;
  feedback: Feedback | null;
  disabled: boolean;
  onPick: (key: string) => void;
  onCite: (c: Feedback["citations"][number]) => void;
  onExplain: () => void;
}) {
  const question = item.question!;
  const correctText =
    feedback &&
    question.options.find((o) => o.key === feedback.correct_key)?.text;

  return (
    <>
      <p className="label learning">Kiểm tra nhanh</p>
      <h2 className="title" style={{ fontSize: 20 }}>
        {question.stem}
      </h2>
      <SaveQuestion
        id={question.id}
        title={question.stem}
        detail={feedback?.explanation}
      />
      <QuizOptions
        options={question.options}
        picked={picked}
        correctKey={feedback?.correct_key ?? null}
        disabled={disabled}
        onPick={onPick}
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
          <p style={{ fontSize: 16, color: "var(--text-2)" }}>
            {feedback.explanation}
          </p>
          {feedback.remediation_note && (
            <p className="note">{feedback.remediation_note}</p>
          )}
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            <button className="btn" onClick={onExplain}>
              Giải thích thêm
            </button>
            {feedback.citations.map((c) => (
              <CitationChip
                key={c.passage_id}
                citation={c}
                onOpen={onCite}
                label={c.page ? `tr. ${c.page}` : (c.article ?? "Nguồn")}
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function EndScreen({ cards }: { cards: number }) {
  return (
    <div
      className="stack center"
      style={{ marginTop: 48, alignItems: "center" }}
    >
      <span
        className="icon-box"
        style={{ width: 64, height: 64, borderRadius: 32 }}
      >
        <Icon name="check" size={30} />
      </span>
      <h2 className="title">Xong chủ đề</h2>
      <p className="muted" style={{ fontSize: 16 }}>
        {cards > 0
          ? `Đã tạo ${cards} thẻ ôn từ câu sai`
          : "Không có thẻ ôn mới."}
      </p>
      <div className="stack" style={{ width: "100%", marginTop: 16 }}>
        {cards > 0 && (
          <Link to="/luyen-tap/on-the" className="btn primary lg block">
            Ôn ngay
          </Link>
        )}
        <Link to="/luyen-tap" className="btn lg block">
          Về Luyện tập
        </Link>
      </div>
    </div>
  );
}
