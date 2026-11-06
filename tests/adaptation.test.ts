import assert from "node:assert/strict";
import { test } from "node:test";
import { adaptationLines, nextPanel } from "../src/lib/adaptation.ts";

test("only the lines the server sent are shown", () => {
  assert.deepEqual(
    adaptationLines({
      graded: { correct: 4, total: 6 },
      mastery_updated: { competencies: 1 },
      cards_created: { n: 2 },
      tomorrow: { reordered: true, top_item: "Đo lường tần suất bệnh" },
    }),
    [
      { label: "Chấm bài", result: "4/6 câu đúng" },
      { label: "Cập nhật mức thành thạo", result: "1 năng lực" },
      { label: "Tạo thẻ ôn từ câu sai", result: "2 thẻ" },
      {
        label: "Sắp xếp lại phiên ngày mai",
        result: "Ưu tiên: Đo lường tần suất bệnh",
      },
    ],
  );
  assert.deepEqual(
    adaptationLines({
      graded: { correct: 6, total: 6 },
      mastery_updated: null,
      cards_created: null,
      tomorrow: null,
    }),
    [{ label: "Chấm bài", result: "6/6 câu đúng" }],
  );
});

test("the next panel never claims a change of difficulty", () => {
  assert.deepEqual(
    nextPanel({ next: { kind: "same_type" }, card_created: true }),
    { title: "Câu tiếp theo", note: "Đã tạo 1 thẻ ôn từ câu này" },
  );
  assert.deepEqual(nextPanel({ next: { kind: "done" }, card_created: false }), {
    title: "Đã xong bộ câu",
    note: null,
  });
  for (const kind of ["harder", "easier"])
    assert.equal(
      nextPanel({ next: { kind }, card_created: false }).title,
      "Câu tiếp theo",
    );
});
