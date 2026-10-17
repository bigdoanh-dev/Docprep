// What a finished practice set changed, and what follows an answer, said in the app's words.
//
// No import here: the module runs as it is under Node for its tests. The payload type it reads is
// declared here and re-exported by api.ts.

// A line that does not apply is null, never a zero.
export type AdaptationSummary = {
  graded: { correct: number; total: number };
  mastery_updated: { competencies: number } | null;
  cards_created: { n: number } | null;
  tomorrow: { reordered: boolean; top_item: string } | null;
};
export type AdaptationLine = { label: string; result: string };

/** The lines of "Phần hỏi đáp đang điều chỉnh": only what the server sent, each with its real result. */
export function adaptationLines(summary: AdaptationSummary): AdaptationLine[] {
  const lines = [
    {
      label: "Chấm bài",
      result: `${summary.graded.correct}/${summary.graded.total} câu đúng`,
    },
  ];
  if (summary.mastery_updated)
    lines.push({
      label: "Cập nhật mức thành thạo",
      result: `${summary.mastery_updated.competencies} năng lực`,
    });
  if (summary.cards_created)
    lines.push({
      label: "Tạo thẻ ôn từ câu sai",
      result: `${summary.cards_created.n} thẻ`,
    });
  if (summary.tomorrow)
    lines.push({
      label: "Sắp xếp lại phiên ngày mai",
      result: `Ưu tiên: ${summary.tomorrow.top_item}`,
    });
  return lines;
}

/** The dark panel after an answer. R1.0 picks a fixed set, so it never says harder or easier. */
export function nextPanel(feedback: {
  next: { kind: string };
  card_created: boolean;
}): { title: string; note: string | null } {
  return {
    title: feedback.next.kind === "done" ? "Đã xong bộ câu" : "Câu tiếp theo",
    note: feedback.card_created ? "Đã tạo 1 thẻ ôn từ câu này" : null,
  };
}
