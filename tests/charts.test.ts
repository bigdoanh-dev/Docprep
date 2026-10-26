import assert from "node:assert/strict";
import { test } from "node:test";
import {
  calendarRows,
  curveGeometry,
  heatLevel,
  share,
} from "../src/lib/charts.ts";

test("heat levels follow the legend", () => {
  assert.deepEqual(
    [0, 1, 15, 16, 45, 46, 75, 76, 600].map(heatLevel),
    [0, 1, 1, 2, 2, 3, 3, 4, 4],
  );
});

test("the calendar starts each row on a Monday", () => {
  const days = Array.from({ length: 56 }, (_, i) => ({
    date: new Date(Date.UTC(2026, 7, 16 + i)).toISOString().slice(0, 10),
    minutes: 0,
  }));
  const rows = calendarRows(days); // 16/08/2026 is a Sunday, 10/10/2026 a Saturday
  assert.equal(rows.length, 9);
  assert.deepEqual(
    rows[0].map((d) => d?.date ?? null),
    [null, null, null, null, null, null, "2026-08-16"],
  );
  assert.equal(rows[8][5]?.date, "2026-10-10");
  assert.equal(rows[8][6], null);
  assert.deepEqual(calendarRows([]), []);
});

test("the curve is drawn from the real points", () => {
  const g = curveGeometry(
    [
      { date: "2026-10-01", recall: 1, kind: "review" },
      { date: "2026-10-06", recall: 0.9, kind: "decay" },
      { date: "2026-10-06", recall: 1, kind: "review" },
      { date: "2026-10-11", recall: 0.75, kind: "decay" },
      { date: "2026-10-21", recall: 0.4, kind: "projected" },
    ],
    200,
    100,
  );
  assert.equal(g.solid, "M0 0 L50 20 L50 0 L100 50");
  assert.equal(g.dashed, "M100 50 L200 100"); // 0.4 is below the floor: clamped to the bottom
  assert.deepEqual(g.today, { x: 100, y: 50 });
});

test("a curve of one review on one day, and no curve, do not break", () => {
  const one = curveGeometry(
    [
      { date: "2026-10-10", recall: 1, kind: "review" },
      { date: "2026-10-10", recall: 1, kind: "decay" },
      { date: "2026-10-17", recall: 0.9, kind: "projected" },
    ],
    200,
    100,
  );
  assert.equal(one.solid, "M0 0 L0 0");
  assert.equal(one.dashed, "M0 0 L200 20");
  assert.deepEqual(curveGeometry([], 200, 100), {
    solid: "",
    dashed: "",
    today: null,
  });
});

test("a share of nothing is nothing", () => {
  assert.deepEqual(
    [share(3, 8), share(0, 0), share(9, 3), share(1, 1)],
    [0.375, 0, 1, 1],
  );
});
