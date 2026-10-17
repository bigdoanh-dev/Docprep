import { localDay, recordActivity } from "./learnerWorkspace";
// Thin JSON client for the backend's /v1 API (proxied under /api by Vite). Every request goes through
// the session, which adds the access token and refreshes it when it has expired.
import { getActor, setActor } from "../app/identity";
import { notifyConsentRequired, session, staffSession } from "./client";
import { demoCall, DemoError, demoStream } from "./demo/store";
import type { Session, Tokens } from "./session";

const BASE = "/api/v1";
function trackLearning(
  method: string,
  path: string,
  body: unknown,
  result: unknown,
  key?: string,
) {
  const data = result as {
    submitted_at?: string;
    attempt_id?: number;
    correct?: boolean;
  };
  if (getActor()?.role !== "learner") return;
  if (/^\/attempts\/\d+\/(submit|results)$/.test(path) && data?.submitted_at) {
    recordActivity(
      `exam:${data.attempt_id}`,
      "exam",
      localDay(new Date(data.submitted_at)),
    );
  } else if (method === "POST" && /\/(responses|reviews)$/.test(path)) {
    const fields = body as { question_id?: string; unit_item_id?: string };
    recordActivity(
      `${path}:${key ?? fields?.question_id ?? fields?.unit_item_id ?? localDay()}`,
      "study",
    );
  }
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, messageVi: string) {
    super(messageVi);
    this.status = status;
    this.code = code;
  }
}

const FALLBACK_MESSAGE = "Có lỗi xảy ra. Vui lòng thử lại.";

const NETWORK_ERROR = () =>
  new ApiError(0, "network", "Không kết nối được máy chủ. Vui lòng thử lại.");

/** The error a failed response carries. A refusal for missing consent also sends the app to the consent screen. */
export async function toApiError(res: Response): Promise<ApiError> {
  let error = new ApiError(res.status, "unknown", FALLBACK_MESSAGE);
  try {
    const body = await res.json();
    if (body?.error)
      error = new ApiError(res.status, body.error.code, body.error.message_vi);
  } catch {
    // not JSON: keep the generic message
  }
  if (error.status === 403 && error.code === "consent_required")
    notifyConsentRequired();
  return error;
}

// `idempotencyKey`: the write carries this key, and the server applies a key once. The caller makes
// the key (keys.ts) when the learner's intent begins and sends the same one if they have to try again.
type Options = { idempotencyKey?: string };

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: Options,
  via: Session = session,
): Promise<T> {
  const actor = getActor();
  if (actor?.mode === "demo") {
    try {
      const result = (await demoCall(
        method,
        path,
        body,
        options?.idempotencyKey,
      )) as T;
      if (actor?.id === getActor()?.id && actor?.mode === getActor()?.mode)
        trackLearning(method, path, body, result, options?.idempotencyKey);
      return result;
    } catch (e) {
      if (e instanceof DemoError) {
        if (e.code === "consent_required") notifyConsentRequired();
        throw new ApiError(e.status, e.code, e.message);
      }
      throw e;
    }
  }
  if (actor && actor.role !== "learner") via = staffSession;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (options?.idempotencyKey)
    headers["Idempotency-Key"] = options.idempotencyKey;
  let res: Response;
  try {
    res = await via.fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw NETWORK_ERROR();
  }
  if (!res.ok) throw await toApiError(res);
  const result = (await res.json()) as T;
  if (actor?.id === getActor()?.id && actor?.mode === getActor()?.mode)
    trackLearning(method, path, body, result, options?.idempotencyKey);
  return result;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown, options?: Options) =>
    request<T>("POST", path, body ?? {}, options),
  put: <T>(path: string, body: unknown, options?: Options) =>
    request<T>("PUT", path, body, options),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};

// Quản lý cấp Bộ: the same API through the staff session.
export const staffApi = {
  get: <T>(path: string) =>
    request<T>("GET", path, undefined, undefined, staffSession),
  post: <T>(path: string, body?: unknown) =>
    request<T>("POST", path, body ?? {}, undefined, staffSession),
  /** A file the server builds, with the name it gives it. */
  async download(
    path: string,
  ): Promise<{ blob: Blob; fileName: string | null }> {
    let res: Response;
    try {
      res = await staffSession.fetch(`${BASE}${path}`);
    } catch {
      throw NETWORK_ERROR();
    }
    if (!res.ok) throw await toApiError(res);
    const fileName =
      /filename="([^"]+)"/.exec(
        res.headers.get("Content-Disposition") ?? "",
      )?.[1] ?? null;
    return { blob: await res.blob(), fileName };
  },
};

/** A POST sent without a token: signing in is the only one. */
export async function publicPost<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw NETWORK_ERROR();
  }
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}

/** Sign out on the server, then forget the tokens whether or not the server could be reached. */
export async function signOut(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } catch {
    // the tokens are forgotten below in any case
  }
  session.signOut();
  staffSession.signOut();
  setActor(null);
}

export { demoStream };

// ---- payload types (mirror the backend) ----

// Lists come in an envelope, so a field can be added beside the items without breaking the client.
export type Listed<T> = { items: T[] };

export type TokenPair = Tokens & {
  expires_in: number;
  role: string;
  consent_required: boolean;
};
export type ConsentText = {
  version: string;
  service_text_vi: string;
  research_text_vi: string;
};

// The ministry dashboard's payload lives with the rules that read it (dashboard.ts).
export type { AdaptationSummary } from "./adaptation";
export type {
  ChatState,
  ChatSuggestion,
  Citation,
  ClarifyOption,
  NearestChapter,
  SearchedSource,
  StepEvent,
  StoredMessage,
  TraceSummary,
} from "./chatTurn";
export type { AdminOverview } from "./dashboard";
export type {
  SessionStep,
  SessionToday,
  StepKind,
  SuggestionAction,
} from "./flow";

// Chat payloads live with the rules that read them (chatTurn.ts).
import type { Citation, StoredMessage } from "./chatTurn";

export type Home = {
  name: string;
  quick_review_count: number;
  quick_review_note_vi: string | null;
  due_cards: number;
  next_mock: {
    form_id: string;
    title: string;
    n_questions: number;
    minutes: number;
    open_attempt_id: number | null;
  } | null;
  tutor_suggestions: {
    kind: string;
    text_vi: string;
    action: SuggestionAction | null;
  }[];
  recent: {
    kind: "unit" | "chat";
    id: string;
    title: string;
    subtitle_vi: string | null;
    progress: number | null;
  }[];
};

// The types of the daily session and of Home's suggestions live with the rules that read them.
import type { SuggestionAction } from "./flow";

export type Me = {
  pseudonym_id: string;
  display_name: string;
  audience: "student" | "graduate";
  organisation: string | null;
  focus_module_ids: string[];
  exam_date: string;
  target_retention: number;
  new_cards_per_day: number;
  max_reviews_per_day: number;
  diagnostic_prompt_dismissed: boolean;
};

export type PassageView = {
  id: string;
  document: string;
  chapter: string | null;
  section: string | null;
  page: number | null;
  article: string | null;
  excerpt: string;
  demo_label: string;
  validity_note: string | null;
};

// A học phần is a blueprint group: `name` is its official text, `short_name` the label for a phone card.
export type Module = {
  id: string;
  name: string;
  short_name: string;
  core_issue_group: number | null;
  coming_soon: boolean;
  units_total: number;
  units_done: number;
  topics_total: number;
};
export type ModuleDetail = {
  id: string;
  name: string;
  short_name: string;
  units: { id: string; topic: string; done: boolean }[];
};

export type Option = { key: string; text: string };

export type Feedback = {
  correct: boolean;
  correct_key: string;
  explanation: string;
  rationales: Record<string, string>;
  citations: Citation[];
  remediation_inserted: boolean;
  remediation_note: string | null;
  card_created: boolean;
};

export type UnitItem = {
  unit_item_id: string;
  kind: "content" | "quiz" | "remediation";
  title: string | null;
  body: string | null;
  citations: Citation[] | null;
  reason: string | null;
  question: { id: string; stem: string; options: Option[] } | null;
  chosen: string | null;
  feedback: Feedback | null;
};

export type UnitView = {
  session_id: number;
  unit_id: string;
  topic: string;
  position: number;
  total: number;
  done: boolean;
  cards_created: number;
  item: UnitItem | null;
};

export type ExamForm = {
  id: string;
  title: string;
  kind: "diagnostic" | "mock" | "demo_short" | "assembled";
  n_questions: number;
  minutes: number;
  attempts_left: number | null;
  last: { attempt_id: number; score: number; total: number } | null;
  open_attempt_id: number | null; // an attempt still running: offer "Làm tiếp"
  open_remaining_s: number | null;
  history: ExamHistoryEntry[]; // finished attempts, newest first
  plan: ExamPlan | null; // assembled forms only: how the next test will be put together
};

export type ExamPlan = {
  composition: { new: number; wrong: number; review: number };
  topics: { name: string; count: number }[];
};

export type ExamHistoryEntry = {
  attempt_id: number;
  submitted_at: string;
  duration_s: number;
  score: number;
  total: number;
  auto_submitted: boolean;
};

export type AttemptView = {
  attempt_id: number;
  title: string;
  deadline_at: string;
  remaining_s: number;
  warning_s: number;
  submitted: boolean;
  questions: { id: string; n: number; stem: string; options: Option[] }[];
  answers: Record<string, { chosen: string | null; flagged: boolean }>;
};

export type ItemStatus = "ok" | "wrong" | "blank";

export type Results = {
  attempt_id: number;
  specialties?: { name: string; correct: number; total: number }[];
  bloom_by_specialty?: {
    module_id: string;
    name: string;
    levels: {
      level: number;
      label_vi: string;
      correct: number;
      total: number;
    }[];
  }[];
  levels?: {
    level: number;
    label_vi: string;
    correct: number;
    total: number;
  }[];
  title: string;
  score: number;
  total: number;
  wrong: number;
  blank: number;
  submitted_at: string;
  duration_s: number;
  auto_submitted: boolean;
  new_cards: number;
  priority_top: string[];
  priority_moved_up: string[];
  items: {
    n: number;
    question_id: string;
    topic: string;
    status: ItemStatus;
  }[];
};

export type ReviewItem = {
  n: number;
  total: number;
  question_id: string;
  stem: string;
  options: (Option & { is_correct: boolean })[];
  chosen: string | null;
  explanation: string;
  rationales: Record<string, string>;
  citations: Citation[];
};

export type DueCard = {
  id: number;
  front: string;
  back: string;
  citation: string;
  source_passage_id: string;
  origin: string;
  module: string;
  preview: Record<"1" | "2" | "3" | "4", number>;
};

export type DueCardList = Listed<DueCard> & { total_due: number };
export type CardReviewResult = {
  card_id: number;
  due_at: string;
  remaining_due: number;
};

export type ChatMessage = StoredMessage;
export type ChatMessageList = Listed<ChatMessage> & {
  next_cursor: string | null;
};
export type ChatSessionSummary = {
  id: number;
  title: string;
  updated_at: string;
};
export type SuggestionAccepted = {
  kind: "practise" | "add_to_tomorrow";
  practice_set_id: number | null;
  for_date: string | null;
};

// ---- Phiên hôm nay ----

export type Remediation = {
  title: string;
  body: string;
  citations: Citation[];
  reason: string;
};
export type PracticeFeedback = {
  correct: boolean;
  correct_key: string;
  explanation: string;
  rationales: Record<string, string>;
  citations: Citation[];
  next: { kind: "same_type" | "harder" | "easier" | "done" };
  card_created: boolean;
  remediation: Remediation | null;
};
export type PracticeItem = {
  question_id: string;
  n: number;
  stem: string;
  options: Option[];
  reason_vi: string;
  chosen: string | null;
  feedback: PracticeFeedback | null;
};
export type PracticeSetView = {
  id: number;
  source: "session" | "chat_suggestion" | "quiz_similar";
  competency_code: string;
  topic: string;
  total: number;
  answered: number;
  completed: boolean;
  items: PracticeItem[];
};

// `generated`: a model wrote the text (it carries the AI mark); otherwise it is the pointer written by code.
export type Hint = { text: string; citations: Citation[]; generated: boolean };
export type Deck = {
  module_id: string;
  name: string;
  short_name: string;
  new: number;
  learning: number;
  due: number;
};

// ---- Tiến độ ----

export type ProgressSkills = {
  days_to_exam: number;
  scope: "latest3" | "all";
  coverage: {
    assessed_topics: number;
    total_topics: number;
    modules: {
      module_id: string;
      short_name: string;
      topics_assessed: number;
      topics_total: number;
    }[];
  };
  priorities: {
    rank: number;
    competency_code: string;
    name: string;
    module_id: string;
    correct: number;
    total: number;
    weakest_vi: string | null;
  }[];
  mock_scores: {
    attempt_id: number;
    title: string;
    submitted_at: string;
    score: number;
    total: number;
  }[];
  specialties?: { name: string; correct: number; total: number }[];
  bloom_by_specialty?: {
    module_id: string;
    name: string;
    levels: {
      level: number;
      label_vi: string;
      correct: number;
      total: number;
    }[];
  }[];
  group_grid: unknown | null; // not shown until open issue 20 is settled
  levels: {
    level: 1 | 2 | 3 | 4 | 5 | 6;
    label_vi: string;
    correct: number;
    total: number;
  }[];
};

export type CurvePoint = {
  date: string;
  recall: number;
  kind: "review" | "decay" | "projected";
};
export type ProgressRhythm = {
  days_to_exam: number;
  week: {
    minutes: number;
    previous_minutes: number;
    study_days: number;
    days_elapsed: number;
  };
  heatmap: { date: string; minutes: number }[];
  memory: {
    recall_rate: number | null;
    window_days: number;
    reviews: number;
    new: number;
    learning: number;
    mastered: number;
    due_today: number;
  };
  curve: CurvePoint[];
  recall_by_module: {
    module_id: string;
    short_name: string;
    now: number;
    in_7_days: number;
  }[];
  due_forecast: { date: string; count: number }[];
  activity: {
    kind: "unit" | "practice" | "chat" | "cards" | "exam";
    title: string;
    occurred_at: string;
    minutes: number | null;
    result_vi: string | null;
  }[];
};
