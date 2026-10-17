// MOCK. Illustrative operating costs for Tổng quan toàn quốc, until the backend records real ones.
// The amounts below are made up and nationwide; nothing here comes from the server. The figures per
// learner divide them by the real counts of the view. Only a type import, with its extension: the
// module runs as it is under Node for its tests.
import type { AiSafety, Kpis } from "./dashboard";

export type CostPart = "ai" | "hosting" | "review" | "support";
/** Đồng spent in one calendar month, nationwide. */
export type MonthCost = Record<CostPart, number>;

export const COST_PARTS: { key: CostPart; label: string }[] = [
  { key: "ai", label: "Mô hình AI" },
  { key: "hosting", label: "Máy chủ và lưu trữ" },
  { key: "review", label: "Thẩm định nội dung" },
  { key: "support", label: "Hỗ trợ và vận hành" },
];

export const MOCK_COSTS: Record<string, MonthCost> = {
  "2026-07": {
    ai: 1_400_000,
    hosting: 14_000_000,
    review: 24_000_000,
    support: 9_000_000,
  },
  "2026-08": {
    ai: 6_200_000,
    hosting: 14_000_000,
    review: 30_000_000,
    support: 11_000_000,
  },
  "2026-09": {
    ai: 6_700_000,
    hosting: 15_500_000,
    review: 21_000_000,
    support: 11_000_000,
  },
  "2026-10": {
    ai: 2_400_000,
    hosting: 15_500_000,
    review: 12_000_000,
    support: 11_000_000,
  },
};

export type CostView = {
  parts: MonthCost;
  total: number;
  previousPeriod: string;
  totalPrevious: number | null;
  perActive: number | null;
  perActivePrevious: number | null;
  perActivated: number | null;
  perPracticeItem: number | null;
  aiPerAnswer: number | null;
  aiPerActive: number | null;
  practicePerActive: number | null;
  mocksPerActive: number | null;
};

const sum = (cost: MonthCost) =>
  cost.ai + cost.hosting + cost.review + cost.support;
const per = (amount: number, n: number) => (n > 0 ? amount / n : null);

/** "2026-08" from "2026-09". */
export function previousPeriod(period: string): string {
  const year = Number(period.slice(0, 4));
  const month = Number(period.slice(5, 7));
  return month === 1
    ? `${year - 1}-12`
    : `${year}-${String(month - 1).padStart(2, "0")}`;
}

/** The month's cost and what it comes to per learner, item and answer; null for a month with no amounts. */
export function costView(
  period: string,
  kpis: Kpis,
  ai: AiSafety | null,
  costs = MOCK_COSTS,
): CostView | null {
  const parts = costs[period];
  if (parts === undefined) return null;
  const total = sum(parts);
  const before = costs[previousPeriod(period)];
  const totalPrevious = before === undefined ? null : sum(before);
  return {
    parts,
    total,
    previousPeriod: previousPeriod(period),
    totalPrevious,
    perActive: per(total, kpis.active_learners),
    perActivePrevious:
      totalPrevious === null
        ? null
        : per(totalPrevious, kpis.active_learners_previous),
    perActivated: per(total, kpis.accounts_activated),
    perPracticeItem: per(total, kpis.practice_items),
    aiPerAnswer: ai === null ? null : per(parts.ai, ai.answers),
    aiPerActive: per(parts.ai, kpis.active_learners),
    practicePerActive: per(kpis.practice_items, kpis.active_learners),
    mocksPerActive: per(kpis.mock_attempts, kpis.active_learners),
  };
}
