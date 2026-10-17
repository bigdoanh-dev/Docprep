// What one answer in Hỏi đáp shows, whether it is arriving now (the stream's events) or was given
// before (a message of the history). The screen only renders this view.
//
// No import here: the module runs as it is under Node for its tests. The payload types it reads are
// declared here and re-exported by api.ts.

export type Citation = {
  n: number;
  passage_id: string;
  document: string;
  chapter: string | null;
  section: string | null;
  page: number | null;
  article: string | null;
};
export type ChatState =
  "answered" | "insufficient_evidence" | "declined" | "needs_clarification";
// One stage of the pipeline that ran for this answer; its label is the server's.
export type StepEvent = {
  id: string;
  kind: string;
  label_vi: string;
  status: "running" | "done";
};
export type TraceSummary = {
  sources: number;
  claims_checked: number;
  claims_removed: number;
};
export type ChatSuggestion = {
  id: number;
  kind: "practise" | "add_to_tomorrow";
  label_vi: string;
  reason_vi: string;
  n_items: number | null;
};
export type SearchedSource = { document: string; range: string };
export type NearestChapter = { passage_id: string; label_vi: string };
export type ClarifyOption = { term: string; label_vi: string; query: string };
// A message of `GET /chat/sessions/{id}/messages`.
export type StoredMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  created_at: string;
  state: ChatState | null;
  format: string | null;
  citations: Citation[];
  notice: string | null;
  trace_summary: TraceSummary | null;
  clarify_options: ClarifyOption[];
  searched: SearchedSource[];
  nearest_chapter: NearestChapter | null;
  suggestions: ChatSuggestion[];
  helpful: boolean | null;
  trace: StepEvent[];
};

export type TurnView = {
  phase: "queued" | "working" | "done" | "failed";
  position: number | null; // the place in line, only while queued
  steps: StepEvent[]; // in the order they first appeared
  text: string | null;
  state: ChatState | null;
  citations: Citation[];
  notice: string | null;
  messageId: number | null;
  summary: TraceSummary | null;
  clarifyOptions: ClarifyOption[];
  searched: SearchedSource[];
  nearestChapter: NearestChapter | null;
  suggestions: ChatSuggestion[];
  helpful: boolean | null;
  error: string | null;
};

export function startTurn(): TurnView {
  return {
    phase: "working",
    position: null,
    steps: [],
    text: null,
    state: null,
    citations: [],
    notice: null,
    messageId: null,
    summary: null,
    clarifyOptions: [],
    searched: [],
    nearestChapter: null,
    suggestions: [],
    helpful: null,
    error: null,
  };
}

/** The view after one event of the answer stream. An event this module does not know changes nothing. */
export function applyEvent(view: TurnView, event: string, data: any): TurnView {
  if (event === "status") {
    return data.status === "queued"
      ? { ...view, phase: "queued", position: data.position ?? null }
      : { ...view, phase: "working", position: null };
  }
  if (event === "step") {
    const at = view.steps.findIndex((s) => s.id === data.id);
    const next = {
      id: data.id,
      kind: data.kind,
      label_vi: data.label_vi,
      status: data.status,
    };
    const steps =
      at === -1
        ? [...view.steps, next]
        : view.steps.map((s, i) => (i === at ? next : s));
    return {
      ...view,
      phase: view.phase === "queued" ? "working" : view.phase,
      position: view.phase === "queued" ? null : view.position,
      steps,
    };
  }
  if (event === "answer") {
    return {
      ...view,
      text: data.text,
      citations: data.citations ?? [],
      notice: data.notice ?? null,
    };
  }
  if (event === "final") {
    return {
      ...view,
      phase: "done",
      position: null,
      state: data.state,
      messageId: data.message_id,
      summary: data.trace_summary ?? null,
      clarifyOptions: data.clarify_options ?? [],
      searched: data.searched ?? [],
      nearestChapter: data.nearest_chapter ?? null,
      suggestions: data.suggestions ?? [],
    };
  }
  return view;
}

/** The stream stopped before its end: say so, and leave no step spinning. */
export function failTurn(view: TurnView, message: string): TurnView {
  return {
    ...view,
    phase: "failed",
    position: null,
    error: message,
    steps: view.steps.map((s) => ({ ...s, status: "done" })),
  };
}

/** An answer of the history, shown as it was when it was given. */
export function fromStored(message: StoredMessage): TurnView {
  return {
    ...startTurn(),
    phase: "done",
    steps: message.trace,
    text: message.text,
    state: message.state,
    citations: message.citations,
    notice: message.notice,
    messageId: message.id,
    summary: message.trace_summary,
    clarifyOptions: message.clarify_options,
    searched: message.searched,
    nearestChapter: message.nearest_chapter,
    suggestions: message.suggestions,
    helpful: message.helpful,
  };
}

/** The chip above an answer: what was checked; or, when the model produced nothing to check, the last thing done. */
export function chipLabel(view: TurnView): string | null {
  if (view.summary)
    return `Đã tra ${view.summary.sources} nguồn · kiểm tra ${view.summary.claims_checked} nhận định`;
  return view.steps.length ? view.steps[view.steps.length - 1].label_vi : null;
}
