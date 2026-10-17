// What a pass through the cards of the session did, said from the ratings the learner gave in it.
// No import here: the module runs as it is under Node for its tests.

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
