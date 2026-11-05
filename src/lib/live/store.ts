// What live mode keeps on this device, per learner, beside what the backend stores: the state of
// flows the backend has no place for (unit runs, practice sets, exam answers before submission,
// chat history), the profile settings it does not hold, and the source passages already seen, so a
// citation can be opened again. Clearing the browser's storage loses these, not the answers,
// cards, mastery or submitted exams, which live on the server.
import { getActor } from "../../app/identity";

export type Passage = {
  document: string;
  chapter: string | null;
  page: number | null;
  text: string;
  kind: string | null;
  stale: boolean;
};

// An item after it was answered: what the tutor and the answer review need to know about it.
export type KnownQuestion = {
  stem: string;
  options: Record<string, string>;
  answer: string;
  explanation: string;
  sources: string[]; // chunk ids
};

export type LiveState = {
  version: 1;
  nextId: number;
  prefs: Record<string, any>;
  units: Record<string, any>;
  practice: Record<string, any>;
  cardSets: Record<string, number>; // card id → the one-item set it is being reviewed with
  recallItems: Record<string, number>; // card id → the item shown for open recall
  attempts: Record<string, any>;
  today: {
    date: string;
    practice_set_id: number | null;
    unit_id: string | null;
  } | null;
  chats: any[];
  suggestions: Record<string, { practice_set_id: number }>;
  questions: Record<string, KnownQuestion>;
  passages: Record<string, Passage>;
  activity: {
    at: string;
    kind: "unit" | "practice" | "chat" | "cards" | "exam";
    title: string;
    seconds: number | null;
    result_vi: string | null;
  }[];
  idempotency: Record<string, unknown>;
};

const LIMITS = {
  passages: 400,
  questions: 500,
  idempotency: 100,
  activity: 1000,
};

const key = () => `yhdp.live.v1:${getActor()?.id}`;

const empty = (): LiveState => ({
  version: 1,
  nextId: 1,
  prefs: { consent_at: new Date().toISOString() },
  units: {},
  practice: {},
  cardSets: {},
  recallItems: {},
  attempts: {},
  today: null,
  chats: [],
  suggestions: {},
  questions: {},
  passages: {},
  activity: [],
  idempotency: {},
});

export function readLive(): LiveState {
  try {
    const saved = JSON.parse(localStorage.getItem(key()) ?? "null");
    if (saved?.version === 1) return { ...empty(), ...saved };
  } catch {
    /* unreadable: start again */
  }
  return empty();
}

// Keeps the most recent `n` entries of a map, in insertion order.
function trim<T>(map: Record<string, T>, n: number): Record<string, T> {
  const keys = Object.keys(map);
  return keys.length <= n
    ? map
    : Object.fromEntries(keys.slice(-n).map((k) => [k, map[k]]));
}

/** Read, change and write back in one go; nothing awaits in between, so no update is lost. */
export function liveTransaction<T>(run: (s: LiveState) => T): T {
  const s = readLive();
  const value = run(s);
  s.passages = trim(s.passages, LIMITS.passages);
  s.questions = trim(s.questions, LIMITS.questions);
  s.idempotency = trim(s.idempotency, LIMITS.idempotency);
  s.activity = s.activity.slice(-LIMITS.activity);
  try {
    localStorage.setItem(key(), JSON.stringify(s));
  } catch {
    // full or blocked storage: the change lasts until reload
  }
  return structuredClone(value);
}

export const nextId = (s: LiveState) => s.nextId++;

export function record(
  s: LiveState,
  kind: LiveState["activity"][number]["kind"],
  title: string,
  seconds: number | null,
  result_vi: string | null = null,
) {
  s.activity.push({
    at: new Date().toISOString(),
    kind,
    title,
    seconds,
    result_vi,
  });
}
