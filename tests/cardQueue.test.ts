import test from "node:test";
import assert from "node:assert/strict";
import { availableCards } from "../src/lib/demo/cardQueue";
const now = Date.parse("2026-11-05T08:00:00Z");
const cards = [0, 0, 2, 3].map((reviews, index) => ({
  id: index + 1,
  suspended: false,
  reviews,
  due_at: "2026-11-05T07:00:00Z",
}));
test("new-card and total-review limits both constrain the available queue", () => {
  assert.deepEqual(
    availableCards(
      cards,
      [],
      { new_cards_per_day: 1, max_reviews_per_day: 2 },
      "2026-11-05",
      now,
    ).map((c) => c.id),
    [1, 3],
  );
  assert.deepEqual(
    availableCards(
      cards,
      [{ card_id: 9, date: "2026-11-05", first_review: true }],
      { new_cards_per_day: 1, max_reviews_per_day: 2 },
      "2026-11-05",
      now,
    ).map((c) => c.id),
    [3],
  );
  assert.deepEqual(
    availableCards(
      cards,
      [],
      { new_cards_per_day: 0, max_reviews_per_day: 0 },
      "2026-11-05",
      now,
    ),
    [],
  );
});
test("limits reset for a different date and exclude future or suspended cards", () => {
  const pool = [
    ...cards,
    { ...cards[0], id: 5, suspended: true },
    { ...cards[0], id: 6, due_at: "2026-11-06T08:00:00Z" },
  ];
  assert.equal(
    availableCards(
      pool,
      [{ card_id: 9, date: "2026-11-04", first_review: true }],
      { new_cards_per_day: 20, max_reviews_per_day: 200 },
      "2026-11-05",
      now,
    ).length,
    4,
  );
});
