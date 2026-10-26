import assert from "node:assert/strict";
import { test } from "node:test";
import { dayMonth, interval, percent, studyTime } from "../src/lib/format.ts";

test("intervals read as the learner says them", () => {
  assert.deepEqual([30, 360, 7200, 345600].map(interval), [
    "<1 phút",
    "6 phút",
    "2 giờ",
    "4 ngày",
  ]);
});

test("study time and shares read the Vietnamese way", () => {
  assert.deepEqual([0, 45, 60, 200].map(studyTime), [
    "0 ph",
    "45 ph",
    "1 g",
    "3 g 20 ph",
  ]);
  assert.deepEqual([0.86, 1, 0, null].map(percent), ["86%", "100%", "0%", "—"]);
  assert.equal(dayMonth("2026-10-09"), "09/10");
});
