import assert from "node:assert/strict";
import { test } from "node:test";
import {
  change,
  chart,
  chartLabel,
  count,
  days,
  delta,
  dong,
  periodLabel,
  score,
  seconds,
  sharePct,
} from "../src/lib/dashboard.ts";
import { costView } from "../src/lib/dashboardCost.ts";

const WEEKS = [
  760, 850, 980, 1120, 1390, 1640, 1890, 2120, 2300, 2440, 2550, 2630,
].map((n, i) => ({
  week_start: new Date(Date.UTC(2026, 6, 20 + 7 * i))
    .toISOString()
    .slice(0, 10),
  active_learners: n,
}));

test("a share is a percentage with a comma decimal, and a dash when it is withheld", () => {
  assert.equal(sharePct(0.58), "58%");
  assert.equal(sharePct(0.972, 1), "97,2%");
  assert.equal(sharePct(0), "0%");
  assert.equal(sharePct(null), "–");
});

test("a median score reads 27/40 with a form size and a percentage without", () => {
  assert.equal(score({ share: 0.675, form_size: 40, learners: 184 }), "27/40");
  assert.equal(score({ share: 0.68, form_size: null, learners: 20 }), "68%");
  assert.equal(score(null), "–");
});

test("a change from the first mock to the latest carries its sign", () => {
  assert.equal(change({ share: 0.1, form_size: 40, learners: 58 }), "+4 câu");
  assert.equal(change({ share: -0.05, form_size: 40, learners: 58 }), "−2 câu");
  assert.equal(change({ share: 0, form_size: 40, learners: 58 }), "0 câu");
  assert.equal(
    change({ share: 0.05, form_size: null, learners: 58 }),
    "+5 điểm %",
  );
  assert.equal(change(null), "–");
});

test("counts use a dot for thousands", () => {
  assert.deepEqual(
    [count(0), count(999), count(3412), count(186400), count(null)],
    ["0", "999", "3.412", "186.400", "–"],
  );
});

test("the change on the month before is a signed percentage, and nothing when there was no month before", () => {
  assert.equal(delta(241, 204), "+18%");
  assert.equal(delta(90, 100), "−10%");
  assert.equal(delta(100, 100), "0%");
  assert.equal(delta(5, 0), null);
});

test("days and seconds keep one decimal only when it says something", () => {
  assert.deepEqual([days(9.8), days(4), days(null)], ["9,8", "4", "–"]);
  assert.deepEqual(
    [seconds(11800), seconds(12000), seconds(null)],
    ["11,8 giây", "12 giây", "–"],
  );
});

test("a period reads as its month", () => {
  assert.equal(periodLabel("2026-09"), "Tháng 9/2026");
});

test("the chart is drawn from the twelve weeks on a round scale", () => {
  const c = chart(WEEKS);
  assert.equal(c.top, 3000);
  assert.deepEqual(
    c.ticks.map((t) => t.label),
    ["0", "1.000", "2.000", "3.000"],
  );
  assert.deepEqual(
    c.ticks.map((t) => t.y),
    [190, 133.3, 76.7, 20],
  );
  const points = c.line.split(" ");
  assert.equal(points.length, 12);
  assert.equal(points[0], "64,146.9");
  assert.equal(points[11], "691,41");
  assert.deepEqual(c.end, { x: 691, y: 41, label: "2.630" });
  assert.equal(c.labels[0].text, "20/7");
  assert.equal(c.labels[11].text, "5/10");
  assert.ok(
    c.area.startsWith("M64 190 L64 146.9") && c.area.endsWith("L691 190 Z"),
  );
});

test("the chart says its first and last values in words", () => {
  assert.equal(
    chartLabel(WEEKS),
    "Học viên hoạt động mỗi tuần: từ 760 (tuần 20/7) đến 2.630 (tuần 5/10)",
  );
});

test("no weeks, one week and weeks of nobody do not break the chart", () => {
  assert.deepEqual(chart([]), {
    top: 3,
    ticks: [],
    line: "",
    area: "",
    end: null,
    labels: [],
  });
  assert.equal(chartLabel([]), "Chưa có dữ liệu hoạt động");
  const one = chart([{ week_start: "2026-09-28", active_learners: 0 }]);
  assert.equal(one.line, "64,190");
  assert.equal(one.top, 3);
});

test("an amount in đồng reads in millions from a million up and to three digits below", () => {
  assert.equal(dong(54_200_000), "54,2 triệu đ");
  assert.equal(dong(61_000_000), "61 triệu đ");
  assert.equal(dong(223_045), "223.000 đ");
  assert.equal(dong(8_222), "8.220 đ");
  assert.equal(dong(null), "–");
});

test("the cost of a month is divided by the counts of the view, and by nobody is a dash", () => {
  const kpis = {
    active_learners: 200,
    active_learners_previous: 100,
    accounts_issued: 400,
    accounts_activated: 250,
    practice_items: 5000,
    mock_attempts: 300,
    mock_median: null,
    cited_claims_share: null,
    cited_claims_target: 0.95,
  };
  const costs = {
    "2026-12": { ai: 1e6, hosting: 2e6, review: 3e6, support: 4e6 },
    "2027-01": { ai: 2e6, hosting: 2e6, review: 3e6, support: 3e6 },
  };
  const view = costView("2027-01", kpis, null, costs);
  assert.equal(view?.total, 10e6);
  assert.equal(view?.previousPeriod, "2026-12");
  assert.equal(view?.perActive, 50_000);
  assert.equal(view?.perActivePrevious, 100_000);
  assert.equal(view?.aiPerAnswer, null);
  assert.equal(view?.practicePerActive, 25);
  assert.equal(
    costView("2026-12", { ...kpis, active_learners: 0 }, null, costs)
      ?.perActive,
    null,
  );
  assert.equal(costView("2026-12", kpis, null, costs)?.totalPrevious, null);
  assert.equal(costView("2025-01", kpis, null, costs), null);
});
