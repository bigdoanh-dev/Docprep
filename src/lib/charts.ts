// The arithmetic behind the charts of Tiến độ. No import here: the module runs as it is under Node
// for its tests. Dates are calendar days ("2026-10-09") and are never passed through a time zone.

const DAY_MS = 86400000;
const dayNumber = (iso: string) =>
  Date.UTC(
    Number(iso.slice(0, 4)),
    Number(iso.slice(5, 7)) - 1,
    Number(iso.slice(8, 10)),
  ) / DAY_MS;
const round1 = (n: number) => Math.round(n * 10) / 10;

/** The shade of a day in the heatmap: 0 none · 1–15 · 16–45 · 46–75 · over 75 minutes. */
export function heatLevel(minutes: number): 0 | 1 | 2 | 3 | 4 {
  if (minutes <= 0) return 0;
  if (minutes <= 15) return 1;
  if (minutes <= 45) return 2;
  return minutes <= 75 ? 3 : 4;
}

/** Consecutive days laid out in weeks, Monday first; the ends are padded with null. */
export function calendarRows<T extends { date: string }>(
  days: T[],
): (T | null)[][] {
  if (days.length === 0) return [];
  const mondayFirst =
    (new Date(dayNumber(days[0].date) * DAY_MS).getUTCDay() + 6) % 7;
  const cells: (T | null)[] = [...Array<null>(mondayFirst).fill(null), ...days];
  while (cells.length % 7 !== 0) cells.push(null);
  return Array.from({ length: cells.length / 7 }, (_, row) =>
    cells.slice(row * 7, row * 7 + 7),
  );
}

/** A part of a whole as 0–1; nothing of nothing is 0. */
export function share(part: number, whole: number): number {
  return whole > 0 ? Math.min(1, Math.max(0, part / whole)) : 0;
}

export const CURVE_FLOOR = 0.5; // the bottom of the memory curve's scale; lower recall is drawn on it

/**
 * The memory curve as two SVG paths in a `width` × `height` box: `solid` through the real points
 * (recall falls to each review, which brings it back to 1), `dashed` from today to the projected
 * point. x runs with the days from the first point to the last; y from recall 1 at the top to
 * CURVE_FLOOR at the bottom.
 */
export function curveGeometry(
  points: { date: string; recall: number; kind: string }[],
  width: number,
  height: number,
): { solid: string; dashed: string; today: { x: number; y: number } | null } {
  if (points.length === 0) return { solid: "", dashed: "", today: null };
  const first = dayNumber(points[0].date);
  const span = dayNumber(points[points.length - 1].date) - first;
  const at = (p: { date: string; recall: number }) => ({
    x: round1(span === 0 ? 0 : ((dayNumber(p.date) - first) / span) * width),
    y: round1(share(1 - p.recall, 1 - CURVE_FLOOR) * height),
  });
  const real = points.filter((p) => p.kind !== "projected").map(at);
  const projected = points.find((p) => p.kind === "projected");
  const today = real.length > 0 ? real[real.length - 1] : null;
  const end = projected ? at(projected) : null;
  return {
    solid: real.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join(" "),
    dashed: today && end ? `M${today.x} ${today.y} L${end.x} ${end.y}` : "",
    today,
  };
}
