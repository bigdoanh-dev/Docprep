type Card = { id: number; suspended: boolean; due_at: string; reviews: number };
export type ReviewEvent = {
  card_id: number;
  date: string;
  first_review: boolean;
};

/** Apply daily limits before exposing a queue; a due new card counts against both limits. */
export function availableCards<T extends Card>(
  cards: T[],
  events: ReviewEvent[],
  limits: { new_cards_per_day: number; max_reviews_per_day: number },
  date: string,
  now: number,
): T[] {
  const today = events.filter((event) => event.date === date);
  let reviewsLeft = Math.max(0, limits.max_reviews_per_day - today.length);
  let newLeft = Math.max(
    0,
    limits.new_cards_per_day -
      today.filter((event) => event.first_review).length,
  );
  const due = cards.filter(
    (card) => !card.suspended && Date.parse(card.due_at) <= now,
  );
  const allowed: T[] = [];
  for (const card of due) {
    if (reviewsLeft === 0) break;
    if (!card.reviews && newLeft === 0) continue;
    allowed.push(card);
    reviewsLeft--;
    if (!card.reviews) newLeft--;
  }
  return allowed;
}
