// What a pass through the cards of the session did, said from the ratings the learner gave in it.
import type { DueCard, DueCardList } from "./api";

/** Load a pass before reviewing it; every request respects the API's 200-card page limit. */
export async function loadCardPass(
  count: number,
  load: (limit: number, offset: number) => Promise<DueCardList>,
): Promise<DueCard[]> {
  const cards: DueCard[] = [];
  while (cards.length < count) {
    const limit = Math.min(200, count - cards.length);
    const page = await load(limit, cards.length);
    const fresh = page.items.filter(
      (c) => !cards.some((loaded) => loaded.id === c.id),
    );
    cards.push(...fresh.slice(0, count - cards.length));
    if (
      !fresh.length ||
      page.items.length < limit ||
      cards.length >= page.total_due
    )
      break;
  }
  return cards;
}

export type PassSummary = {
  title: string;
  recall: string | null;
  forgotten: string | null;
};

/** `ratings` are this pass's ratings in order: 1 Học lại, 2 Khó, 3 Tốt, 4 Dễ. */
export function passSummary(ratings: number[]): PassSummary {
  const n = ratings.length;
  if (n === 0)
    return {
      title: "Không còn thẻ nào đến hạn",
      recall: null,
      forgotten: null,
    };
  const forgotten = ratings.filter((r) => r === 1).length;
  return {
    title: `Xong ${n} thẻ`,
    recall: `Nhớ đúng ${n - forgotten}/${n}`,
    forgotten:
      forgotten > 0
        ? `${forgotten} thẻ bạn quên sẽ quay lại trong hôm nay`
        : null,
  };
}
