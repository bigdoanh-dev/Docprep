// Where the daily session and Home's suggestions lead.
//
// No React, DOM or Vite import here, and no import at all: the module runs as it is under Node for
// its tests. The payload types it reads are declared here and re-exported by api.ts.

export type StepKind = "cards" | "practice" | "continue";
export type SessionStep = {
  kind: StepKind;
  count: number;
  minutes: number;
  reason_vi: string;
  done: boolean;
  practice_set_id: number | null;
  unit_id: string | null;
};
// A step with nothing behind it is left out, so there may be fewer than three.
export type SessionToday = {
  local_date: string;
  steps: SessionStep[];
  total_minutes: number;
};
// What a Home suggestion links to.
export type SuggestionAction = {
  label_vi: string;
  target: "cards" | "unit" | "practice_set" | "session";
  id: string | null;
};

export const STEP_LABEL: Record<StepKind, string> = {
  cards: "Thẻ ôn",
  practice: "Luyện điểm yếu",
  continue: "Học tiếp",
};

/** The screen a Home suggestion opens. A suggestion is a link: nothing is applied for the learner. */
export function suggestionPath(action: SuggestionAction): string {
  if (action.target === "unit") return `/luyen-tap/${action.id}`;
  if (action.target === "practice_set") return `/luyen-tap/bo-cau/${action.id}`;
  return action.target === "cards" ? "/luyen-tap/on-the" : "/phien";
}

/** The route of a step. Step 3 is the unit itself, shown inside the session. */
export function stepPath(step: SessionStep): string {
  if (step.kind === "cards") return "/phien/the";
  return step.kind === "practice"
    ? "/phien/luyen"
    : `/luyen-tap/${step.unit_id}?phien=1`;
}

/** The first step not done yet; with `after`, the first one not done that comes later than that step. */
export function nextStep(
  session: SessionToday,
  after?: StepKind,
): SessionStep | null {
  const from =
    after === undefined
      ? 0
      : session.steps.findIndex((s) => s.kind === after) + 1;
  return session.steps.slice(from).find((s) => !s.done) ?? null;
}

/** The step bar: one entry per step the session has, as seen from the step being shown. */
export function stepStates(
  session: SessionToday,
  current: StepKind,
): { kind: StepKind; label: string; state: "done" | "current" | "todo" }[] {
  return session.steps.map((s) => ({
    kind: s.kind,
    label: STEP_LABEL[s.kind],
    state: s.kind === current ? "current" : s.done ? "done" : "todo",
  }));
}

/**
 * The green tile on Home. With something to review it says how much; with nothing, it says what is
 * left of today's session, or that the session is done. It never promises a step that is not there.
 */
export function homeTile(
  count: number,
  note: string | null,
  session: SessionToday | undefined,
): { title: string; sub: string | null } {
  if (count > 0) return { title: `Ôn nhanh ${count} câu`, sub: note };
  if (!session) return { title: "Phiên hôm nay", sub: null };
  const next = nextStep(session);
  return {
    title: "Phiên hôm nay",
    sub: next
      ? `${STEP_LABEL[next.kind]} · khoảng ${next.minutes} phút`
      : "Đã xong phiên hôm nay",
  };
}
