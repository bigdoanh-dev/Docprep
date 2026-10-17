import { useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import {
  ReviewActions,
  ReviewCard,
  type Rating,
} from "../../components/ReviewCard";
import { SessionHeader } from "../../components/SessionHeader";
import { LoadError, Loading } from "../../components/Status";
import {
  api,
  type CardReviewResult,
  type DueCard,
  type DueCardList,
  type ProgressRhythm,
  type SessionToday,
} from "../../lib/api";
import { passSummary } from "../../lib/cardPass";
import { STEP_LABEL, nextStep, stepPath } from "../../lib/flow";
import { useLoad } from "../../lib/hooks";
import { newKey } from "../../lib/keys";

// Phiên hôm nay, step 1 (FR-LRN-34): one pass through the cards that are due, each shown once. A
// card rated "Học lại" comes back later today, not within this pass.
export function SessionCards() {
  const { data, error, reload } = useLoad(async () => {
    const session = await api.get<SessionToday>("/session/today");
    const step = session.steps.find((s) => s.kind === "cards");
    const queue = step
      ? (await api.get<DueCardList>(`/cards/due?limit=${step.count}`)).items
      : [];
    return { session, hasStep: step !== undefined, queue };
  }, []);
  const [queue, setQueue] = useState<DueCard[]>(); // the pass, once a card has been suspended out of it
  const [ratings, setRatings] = useState<number[]>([]);
  const [revealed, setRevealed] = useState(false);
  const [sent, setSent] = useState<Rating | null>(null); // the rating sent for the card shown, until it is confirmed
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string>();
  const revealedAt = useRef(0); // when the answer was shown: the review time sent with the rating
  const ratingKey = useRef(""); // one key per card shown: a rating sent again is still one rating

  if (error)
    return (
      <div className="screen">
        <div className="body">
          <LoadError message={error} onRetry={reload} />
        </div>
      </div>
    );
  if (!data)
    return (
      <div className="screen">
        <div className="body">
          <Loading />
        </div>
      </div>
    );
  if (!data.hasStep) return <Navigate to="/phien" replace />;

  const cards = queue ?? data.queue;
  const card = cards[ratings.length];

  const reveal = () => {
    revealedAt.current = Date.now();
    ratingKey.current = newKey();
    setRevealed(true);
  };

  const act = async (action: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setActionError(undefined);
    try {
      await action();
      setRevealed(false);
      setSent(null);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const rate = (rating: Rating) =>
    act(async () => {
      setSent(rating);
      await api.post<CardReviewResult>(
        `/cards/${card.id}/reviews`,
        { rating: Number(rating), time_ms: Date.now() - revealedAt.current },
        { idempotencyKey: ratingKey.current },
      );
      setRatings([...ratings, Number(rating)]);
    });

  const suspend = () =>
    act(async () => {
      await api.patch(`/cards/${card.id}`, { suspended: true });
      setQueue(cards.filter((c) => c.id !== card.id));
    });

  return (
    <div className="screen">
      <SessionHeader
        session={data.session}
        current="cards"
        countLabel={
          card ? `Thẻ ${ratings.length + 1}/${cards.length}` : undefined
        }
      />
      <div className="body stack">
        {card ? (
          <ReviewCard
            key={card.id}
            card={card}
            revealed={revealed}
            busy={busy}
            onSuspend={suspend}
            prompt="Nhớ lại câu trả lời trong đầu, rồi lật thẻ."
          />
        ) : (
          <PassDone session={data.session} ratings={ratings} />
        )}
        {actionError && (
          <p className="warn" role="alert">
            {actionError}
          </p>
        )}
      </div>
      {card && (
        <ReviewActions
          revealed={revealed}
          revealLabel="Lật thẻ"
          onReveal={reveal}
          onRate={rate}
          busy={busy}
          sent={sent}
        />
      )}
    </div>
  );
}

function PassDone({
  session,
  ratings,
}: {
  session: SessionToday;
  ratings: number[];
}) {
  const summary = passSummary(ratings);
  // Tomorrow's count is a nice-to-know: the screen does not wait for it and says nothing if it fails.
  const { data: rhythm } = useLoad(
    () => api.get<ProgressRhythm>("/progress/rhythm"),
    [],
  );
  const tomorrow =
    ratings.length > 0 ? rhythm?.due_forecast[1]?.count : undefined;
  const next = nextStep(session, "cards");
  const position = next
    ? session.steps.findIndex((s) => s.kind === next.kind) + 1
    : 0;
  return (
    <div className="stack" style={{ marginTop: 24 }}>
      <h2 className="title center">{summary.title}</h2>
      {summary.recall && (
        <p className="center" style={{ fontSize: 16 }}>
          {summary.recall}
        </p>
      )}
      {summary.forgotten && <p className="note center">{summary.forgotten}</p>}
      {tomorrow !== undefined && (
        <p className="muted center">Ngày mai · {tomorrow} thẻ đến hạn</p>
      )}
      {next && (
        <div className="card stack" style={{ marginTop: 12 }}>
          <p className="label">
            Bước {position} / {session.steps.length}
          </p>
          <p className="h2">{STEP_LABEL[next.kind]}</p>
          <p className="muted">
            {next.count} {next.kind === "continue" ? "mục" : "câu"} · khoảng{" "}
            {next.minutes} phút
          </p>
        </div>
      )}
      <Link
        to={next ? stepPath(next) : "/phien"}
        className="btn primary lg block"
      >
        Tiếp tục
      </Link>
      <Link to="/" className="btn lg block">
        Dừng ở đây, về trang chủ
      </Link>
    </div>
  );
}
