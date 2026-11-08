import test from "node:test";
import assert from "node:assert/strict";
import { learningMatrix } from "../src/lib/learningAnalytics";

test("live three-band assessments retain server labels in both matrix perspectives", () => {
  const levels = [
    { level: 1, label_vi: "Nhớ, Hiểu", correct: 2, total: 6 },
    { level: 2, label_vi: "Vận dụng", correct: 1, total: 3 },
    { level: 3, label_vi: "Phân tích, Đánh giá", correct: 0, total: 1 },
  ];
  const groups = [{ module_id: "g1", name: "Dự phòng", levels }];
  const specialties = learningMatrix(groups, "specialty", levels);
  assert.deepEqual(
    specialties.columns.map((c) => c.label),
    levels.map((l) => l.label_vi),
  );
  assert.equal(specialties.rows[0].cells[1].bloom, "Vận dụng");
  assert.equal(specialties.rows[0].cells[1].correct, 1);
  const bloom = learningMatrix(groups, "bloom", levels);
  assert.equal(bloom.rows.length, 3);
  assert.equal(bloom.rows[1].label, "Vận dụng");
  assert.deepEqual(bloom.rows[1].cells, [specialties.rows[0].cells[1]]);
});
