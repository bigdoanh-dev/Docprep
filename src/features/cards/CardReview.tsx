import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../../components/Icon";
import {
  ReviewActions,
  ReviewCard,
  type Rating,
} from "../../components/ReviewCard";
import { LoadError, Loading } from "../../components/Status";
import { api, type CardReviewResult, type DueCardList } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { newKey } from "../../lib/keys";

// Ôn thẻ, deck mode (FR-LRN-34): the whole due queue, one card at a time, scheduled by FSRS on the
// server. The queue is read again after each rating: a card rated "Học lại" comes back when its
// short step is due.
export function CardReview() {
  const {
    data: due,
    error,
    reload,
  } = useLoad(() => api.get<DueCardList>("/cards/due"), []);
  const [revealed, setRevealed] = useState(false);
  const [sent, setSent] = useState<Rating | null>(null); // the rating sent for the card shown, until it is confirmed
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string>();
  const [reviewed, setReviewed] = useState(0);
  const queue = due?.items;
  const card = queue?.[0];
  const revealedAt = useRef(0); // when the answer was shown: the review time sent with the rating
  // One key per card shown: a rating sent again because its answer was lost is still one rating.
  const ratingKey = useRef("");

  useEffect(() => {
    setRevealed(false);
    setSent(null);
  }, [card?.id]);

  const reveal = () => {
    revealedAt.current = Date.now();
    ratingKey.current = newKey();
    setRevealed(true);
  };

  const act = async (action: () => Promise<void>) => {
    if (!card || busy) return;
    setBusy(true);
    setActionError(undefined);
    try {
      await action();
      setSent(null);
      reload();
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
        `/cards/${card!.id}/reviews`,
        { rating: Number(rating), time_ms: Date.now() - revealedAt.current },
        { idempotencyKey: ratingKey.current },
      );
      setReviewed((n) => n + 1);
    });

  const suspend = () =>
    act(async () => {
      await api.patch(`/cards/${card!.id}`, { suspended: true });
    });

  return (
    <div className="screen">
      <header className="topbar">
        <Link
          to="/luyen-tap/bo-the"
          className="icon-btn"
          aria-label="Về Bộ thẻ"
        >
          <Icon name="left" />
        </Link>
        <h1>Ôn thẻ</h1>
        {due && (
          <span className="tag" style={{ fontSize: 14 }}>
            {due.total_due} thẻ đến hạn
          </span>
        )}
      </header>
      <div className="body stack">
        {error && <LoadError message={error} onRetry={reload} />}
        {!queue && !error && <Loading />}

        {queue && !card && (
          <div className="card stack center" style={{ padding: 28 }}>
            <h2 className="h2">
              {reviewed > 0 ? "Xong thẻ hôm nay" : "Chưa có thẻ đến hạn"}
            </h2>
            <p className="muted">
              {reviewed > 0
                ? `Đã ôn ${reviewed} lượt thẻ.`
                : "Thẻ ôn được tạo từ những câu bạn trả lời sai trong Luyện tập và Thi thử."}
            </p>
            <Link to="/luyen-tap" className="btn block">
              Học chủ đề mới
            </Link>
            <Link to="/" className="btn block">
              Về trang chủ
            </Link>
          </div>
        )}

        {card && (
          <ReviewCard
            key={card.id}
            card={card}
            revealed={revealed}
            busy={busy}
            onSuspend={suspend}
          />
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
          revealLabel="Hiện đáp án"
          onReveal={reveal}
          onRate={rate}
          busy={busy}
          sent={sent}
        />
      )}
    </div>
  );
}
