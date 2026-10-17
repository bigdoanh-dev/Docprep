// Quản lý cấp Bộ · Tổng quan toàn quốc: the payload and how its figures are written and drawn.
// No import here: the module runs as it is under Node for its tests. Numbers are written the
// Vietnamese way (3.412 · 97,2%); a figure the server withheld is a dash, never a zero.

export type FilterOption = { value: string; label_vi: string };
export type ScoreMedian = {
  share: number;
  form_size: number | null;
  learners: number;
};
export type WeekPoint = { week_start: string; active_learners: number };
export type Retention = {
  weeks: 1 | 4 | 8;
  share: number | null;
  learners: number;
};
export type Alert = {
  kind: "low_activation" | "slow_review" | "old_reports";
  title_vi: string;
  detail_vi: string;
};
export type ModuleAccuracy = {
  module_id: string;
  short_name: string;
  share: number | null;
  low: boolean;
  learners: number;
};
export type SchoolRow = {
  code: string;
  name: string;
  region: string | null;
  accounts_issued: number;
  accounts_activated: number;
  activation_low: boolean;
  weekly_active: number;
  mock_attempts: number;
  mock_median: ScoreMedian | null;
  first_to_latest: ScoreMedian | null;
};
export type Kpis = {
  active_learners: number;
  active_learners_previous: number;
  accounts_issued: number;
  accounts_activated: number;
  practice_items: number;
  mock_attempts: number;
  mock_median: ScoreMedian | null;
  cited_claims_share: number | null;
  cited_claims_target: number;
};
export type QuestionBank = {
  approved: number;
  in_review: number;
  draft: number;
  rejected: number;
  issues_covered: number;
  issues_total: number;
  min_approved_per_issue: number;
  round1_median_days: number | null;
  round2_median_days: number | null;
  round2_target_days: number;
  rounds_agree_share: number | null;
  reports_received: number;
  reports_resolved: number;
};
export type AiSafety = {
  answers: number;
  model_versions: string[];
  corpus_versions: string[];
  cited_claims_share: number | null;
  cited_claims_target: number;
  insufficient_share: number | null;
  declined_share: number | null;
  flagged_share: number | null;
  reports_per_1000: number | null;
};
export type Compliance = {
  chat_p95_ms: number | null;
  chat_target_ms: number;
  research_consent_learners: number;
  research_consent_share: number | null;
  consent_withdrawals: number;
  deletion_requests: number;
  deletion_median_days: number | null;
};
export type Selected = {
  period: string;
  school: string | null;
  audience: string | null;
  region: string | null;
};
export type AdminOverview = {
  period: string;
  computed_at: string;
  sample_data: boolean;
  suppressed: boolean;
  suppression_min: number;
  selected: Selected;
  filters: {
    periods: FilterOption[];
    schools: FilterOption[];
    audiences: FilterOption[];
    regions: FilterOption[];
  };
  kpis: Kpis | null;
  weekly_active: { weeks: WeekPoint[]; retention: Retention[] } | null;
  alerts: Alert[];
  accuracy_by_module: { learners: number; items: ModuleAccuracy[] } | null;
  question_bank: QuestionBank | null;
  ai_safety: AiSafety | null;
  schools: {
    rows: SchoolRow[];
    hidden: { name: string; region: string | null; learners: number }[];
  } | null;
  compliance: Compliance | null;
};

export const DASH = "–";
const MINUS = "−";

const comma = (n: number, digits: number) =>
  n.toFixed(digits).replace(".", ",");
const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `${MINUS}${-n}` : "0");

/** "3.412": a count with a dot for thousands. */
export function count(n: number | null): string {
  return n === null
    ? DASH
    : String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** "58%", or "97,2%" with one digit. */
export function sharePct(share: number | null, digits = 0): string {
  return share === null ? DASH : `${comma(share * 100, digits)}%`;
}

/** A median score: "27/40" when every attempt behind it had 40 questions, else a percentage. */
export function score(median: ScoreMedian | null): string {
  if (median === null) return DASH;
  return median.form_size === null
    ? sharePct(median.share)
    : `${Math.round(median.share * median.form_size)}/${median.form_size}`;
}

/** The change from a learner's first mock to their latest: "+4 câu", or "+5 điểm %" without a form size. */
export function change(c: ScoreMedian | null): string {
  if (c === null) return DASH;
  return c.form_size === null
    ? `${signed(Math.round(c.share * 100))} điểm %`
    : `${signed(Math.round(c.share * c.form_size))} câu`;
}

/** The change on the month before, "+18%"; null when the month before had nobody. */
export function delta(current: number, previous: number): string | null {
  return previous > 0
    ? `${signed(Math.round(((current - previous) / previous) * 100))}%`
    : null;
}

const oneDecimal = (n: number) =>
  Math.round(n * 10) % 10 === 0 ? String(Math.round(n)) : comma(n, 1);

/** "9,8" or "4". */
export function days(n: number | null): string {
  return n === null ? DASH : oneDecimal(n);
}

/** An amount in đồng: "54,2 triệu đ" from a million up, three significant digits below ("223.000 đ"). */
export function dong(n: number | null): string {
  if (n === null) return DASH;
  if (n >= 1e9) return `${oneDecimal(n / 1e9)} tỷ đ`;
  if (n >= 1e6) return `${oneDecimal(n / 1e6)} triệu đ`;
  const unit = 10 ** Math.max(0, Math.floor(Math.log10(Math.max(1, n))) - 2);
  return `${count(Math.round(n / unit) * unit)} đ`;
}

/** "11,8 giây" from milliseconds. */
export function seconds(ms: number | null): string {
  return ms === null ? DASH : `${oneDecimal(ms / 1000)} giây`;
}

/** "Tháng 9/2026" from "2026-09". */
export function periodLabel(period: string): string {
  return `Tháng ${Number(period.slice(5, 7))}/${period.slice(0, 4)}`;
}

/** "20/7" from the calendar day "2026-07-20", by its own digits. */
export function weekLabel(isoDate: string): string {
  return `${Number(isoDate.slice(8, 10))}/${Number(isoDate.slice(5, 7))}`;
}

// The chart's box, as in the mock: a 720 × 230 viewBox, the plot from x 64 to 691 and y 190 up to 20.
export const CHART = {
  width: 720,
  height: 230,
  left: 64,
  right: 691,
  bottom: 190,
  top: 20,
  gridLeft: 48,
  gridRight: 710,
};
const GRID_STEPS = 3;
const round1 = (n: number) => Math.round(n * 10) / 10;

/** The smallest of 1, 2, 5 × a power of ten that three of cover `max`. */
function step(max: number): number {
  const raw = max / GRID_STEPS;
  if (raw <= 1) return 1;
  const power = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) as number;
}

export type ChartGeometry = {
  top: number;
  ticks: { y: number; label: string }[];
  line: string;
  area: string;
  end: { x: number; y: number; label: string } | null;
  labels: { x: number; text: string }[];
};

/** The weekly line: polyline points, the area under it, the gridline labels and the week labels. */
export function chart(weeks: WeekPoint[]): ChartGeometry {
  const top =
    step(Math.max(0, ...weeks.map((w) => w.active_learners))) * GRID_STEPS;
  if (weeks.length === 0)
    return { top, ticks: [], line: "", area: "", end: null, labels: [] };
  const plot = CHART.bottom - CHART.top;
  const gap =
    weeks.length > 1 ? (CHART.right - CHART.left) / (weeks.length - 1) : 0;
  const points = weeks.map((w, i) => ({
    x: round1(CHART.left + i * gap),
    y: round1(CHART.bottom - (w.active_learners / top) * plot),
  }));
  const last = points[points.length - 1];
  return {
    top,
    ticks: Array.from({ length: GRID_STEPS + 1 }, (_, k) => ({
      y: round1(CHART.bottom - (k / GRID_STEPS) * plot),
      label: count((top / GRID_STEPS) * k),
    })),
    line: points.map((p) => `${p.x},${p.y}`).join(" "),
    area: `M${points[0].x} ${CHART.bottom} L${points.map((p) => `${p.x} ${p.y}`).join(" L")} L${last.x} ${CHART.bottom} Z`,
    end: { ...last, label: count(weeks[weeks.length - 1].active_learners) },
    labels: weeks.map((w, i) => ({
      x: points[i].x,
      text: weekLabel(w.week_start),
    })),
  };
}

/** What the chart shows, for a reader who cannot see it: the real first and last values. */
export function chartLabel(weeks: WeekPoint[]): string {
  if (weeks.length === 0) return "Chưa có dữ liệu hoạt động";
  const first = weeks[0];
  const last = weeks[weeks.length - 1];
  return (
    `Học viên hoạt động mỗi tuần: từ ${count(first.active_learners)} (tuần ${weekLabel(first.week_start)}) ` +
    `đến ${count(last.active_learners)} (tuần ${weekLabel(last.week_start)})`
  );
}
