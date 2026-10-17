import assert from "node:assert/strict";
import { test } from "node:test";
import {
  homeTile,
  nextStep,
  stepPath,
  stepStates,
  suggestionPath,
  type SessionStep,
  type SessionToday,
  type StepKind,
} from "../src/lib/flow.ts";

const step = (
  kind: StepKind,
  done: boolean,
  extra: Partial<SessionStep> = {},
): SessionStep => ({
  kind,
  count: 6,
  minutes: 8,
  reason_vi: "r",
  done,
  practice_set_id: null,
  unit_id: null,
  ...extra,
});
const today = (...steps: SessionStep[]): SessionToday => ({
  local_date: "2026-10-12",
  steps,
  total_minutes: 18,
});

test("a suggestion links to the screen that shows it", () => {
  assert.equal(
    suggestionPath({ label_vi: "Xem thẻ", target: "cards", id: null }),
    "/luyen-tap/on-the",
  );
  assert.equal(
    suggestionPath({ label_vi: "Học", target: "unit", id: "u-dt-02" }),
    "/luyen-tap/u-dt-02",
  );
  assert.equal(
    suggestionPath({ label_vi: "Luyện", target: "practice_set", id: "31" }),
    "/luyen-tap/bo-cau/31",
  );
  assert.equal(
    suggestionPath({ label_vi: "Ôn", target: "session", id: null }),
    "/phien",
  );
});

test("each step has its route", () => {
  assert.equal(stepPath(step("cards", false)), "/phien/the");
  assert.equal(stepPath(step("practice", false)), "/phien/luyen");
  assert.equal(
    stepPath(step("continue", false, { unit_id: "u-dt-02" })),
    "/luyen-tap/u-dt-02?phien=1",
  );
});

test("the session opens at its first unfinished step", () => {
  const s = today(
    step("cards", true),
    step("practice", false),
    step("continue", false, { unit_id: "u" }),
  );
  assert.equal(nextStep(s)?.kind, "practice");
  assert.equal(nextStep(s, "practice")?.kind, "continue");
  assert.equal(nextStep(s, "continue"), null);
  assert.equal(nextStep(today()), null);
  assert.equal(nextStep(today(step("cards", true))), null);
});

test("the bar shows only the steps the session has", () => {
  const s = today(
    step("cards", true),
    step("continue", false, { unit_id: "u" }),
  );
  assert.deepEqual(stepStates(s, "continue"), [
    { kind: "cards", label: "Thẻ ôn", state: "done" },
    { kind: "continue", label: "Học tiếp", state: "current" },
  ]);
  assert.deepEqual(
    stepStates(
      today(step("cards", false), step("practice", false)),
      "cards",
    ).map((x) => x.state),
    ["current", "todo"],
  );
});

test("the Home tile promises only what is left of the session", () => {
  const left = today(
    step("cards", true),
    step("continue", false, { unit_id: "u", minutes: 9 }),
  );
  const done = today(
    step("cards", true),
    step("continue", true, { unit_id: "u" }),
  );
  assert.deepEqual(homeTile(7, "2 thẻ mới từ câu bạn trả lời sai", left), {
    title: "Ôn nhanh 7 câu",
    sub: "2 thẻ mới từ câu bạn trả lời sai",
  });
  assert.deepEqual(homeTile(7, null, done), {
    title: "Ôn nhanh 7 câu",
    sub: null,
  });
  assert.deepEqual(homeTile(0, null, left), {
    title: "Phiên hôm nay",
    sub: "Học tiếp · khoảng 9 phút",
  });
  assert.deepEqual(homeTile(0, null, done), {
    title: "Phiên hôm nay",
    sub: "Đã xong phiên hôm nay",
  });
  assert.deepEqual(homeTile(0, null, today()), {
    title: "Phiên hôm nay",
    sub: "Đã xong phiên hôm nay",
  });
  assert.deepEqual(homeTile(0, null, undefined), {
    title: "Phiên hôm nay",
    sub: null,
  }); // the session is not known yet
});
