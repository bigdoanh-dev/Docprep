import { test } from "node:test";
import assert from "node:assert/strict";
import { summarizeAnswers } from "../src/lib/learningAnalytics.ts";
import { streak, localDay } from "../src/lib/learnerWorkspace.ts";
test("streak deduplicates days, preserves yesterday, breaks gaps and respects Vietnam midnight", () => {
  assert.equal(
    streak(
      ["2026-10-12", "2026-10-13", "2026-10-13", "2026-10-14"],
      "2026-10-14",
    ),
    3,
  );
  assert.equal(streak(["2026-10-12", "2026-10-13"], "2026-10-14"), 2);
  assert.equal(streak(["2026-10-12"], "2026-10-14"), 0);
  assert.equal(streak(["2026-10-12", "2026-10-14"], "2026-10-14"), 1);
  assert.equal(streak(["2025-12-31", "2026-01-01"], "2026-01-01"), 2);
  assert.equal(localDay(new Date("2026-10-13T17:00:00Z")), "2026-10-14");
});
test("specialty and Bloom counts come from metadata; missing assessment stays empty", () => {
  const groups = [
    { id: 1, short_name: "Dự phòng", issues: [{ id: 1 }] },
    { id: 2, short_name: "Cấp cứu", issues: [{ id: 2 }] },
  ];
  const questions = [
    { id: "q1", bloom_level: 1, competency_code: "FND" },
    { id: "q2", bloom_level: 3, competency_code: "CI-02" },
  ];
  const data = summarizeAnswers(
    [
      { question_id: "q1", correct: true },
      { question_id: "q2", correct: false },
      { question_id: "unknown", correct: true },
    ],
    questions,
    groups,
  );
  assert.deepEqual(
    data.specialties.map((s) => [s.correct, s.total]),
    [
      [1, 1],
      [0, 1],
    ],
  );
  assert.deepEqual(
    data.levels.map((l) => [l.correct, l.total]),
    [
      [1, 1],
      [0, 0],
      [0, 1],
      [0, 0],
      [0, 0],
      [0, 0],
    ],
  );
  assert.deepEqual(
    data.bloom_by_specialty[0].levels.map((l) => l.total),
    [1, 0, 0, 0, 0, 0],
  );
  assert.deepEqual(
    data.bloom_by_specialty[1].levels.map((l) => l.total),
    [0, 0, 1, 0, 0, 0],
  );
  assert.equal(
    summarizeAnswers([], questions, groups).levels.every((l) => l.total === 0),
    true,
  );
});

test("matrix transpose preserves assessed zero, missing levels and cell identity", async () => {
  const { learningMatrix, assessmentPercent } =
    await import("../src/lib/learningAnalytics.ts");
  const groups = [
    {
      module_id: "g1",
      name: "Dự phòng",
      levels: [
        { level: 3, label_vi: "Vận dụng", correct: 1, total: 2 },
        { level: 1, label_vi: "Ghi nhớ", correct: 0, total: 3 },
      ],
    },
    { module_id: "g2", name: "Cấp cứu", levels: [] },
  ];
  const normal = learningMatrix(groups, "specialty");
  const transposed = learningMatrix(groups, "bloom");
  assert.equal(normal.rows.length, 2);
  assert.equal(normal.columns.length, 6);
  assert.equal(transposed.rows.length, 6);
  assert.equal(transposed.columns.length, 2);
  for (let row = 0; row < 2; row++) {
    for (let col = 0; col < 6; col++) {
      assert.deepEqual(
        normal.rows[row].cells[col],
        transposed.rows[col].cells[row],
      );
    }
  }
  assert.equal(assessmentPercent(normal.rows[0].cells[0]), 0);
  assert.equal(assessmentPercent(normal.rows[0].cells[1]), null);
  assert.equal(assessmentPercent(normal.rows[0].cells[2]), 50);
  assert.equal(normal.rows[0].cells[2].id, "g1:3");
  assert.equal(
    normal.rows.flatMap((r) => r.cells).reduce((sum, c) => sum + c.total, 0),
    5,
  );
  assert.equal(
    learningMatrix([groups[1]], "bloom").rows.every(
      (r) => r.cells[0].total === 0,
    ),
    true,
  );
  assert.deepEqual(learningMatrix([], "specialty").rows, []);
});
