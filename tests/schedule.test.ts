import { test } from "node:test";
import assert from "node:assert/strict";
import { scheduleError } from "../src/features/management/schedule.ts";
test("schedule rejects absent and invalid dates", () => {
  assert.ok(scheduleError("", "", 50));
  assert.ok(scheduleError("invalid", "2026-10-20T08:00", 50));
});
test("schedule rejects backwards, too short, fractional and out-of-range duration", () => {
  assert.ok(scheduleError("2026-10-20T08:00", "2026-10-20T07:00", 50));
  assert.ok(scheduleError("2026-10-20T08:00", "2026-10-20T08:10", 50));
  assert.ok(scheduleError("2026-10-20T08:00", "2026-10-20T10:00", 12.5));
  assert.ok(scheduleError("2026-10-20T08:00", "2026-10-20T10:00", 0));
});
test("schedule accepts an opening window exactly fitting the duration", () => {
  assert.equal(scheduleError("2026-10-20T08:00", "2026-10-20T08:50", 50), null);
});
