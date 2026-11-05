// Live mode: the screens' /v1 contract (docs/handoffs/mobile-backend-handoff.md) served by the
// repo's own backend. Each /v1 call becomes one or more /api calls, and the answer is put in the
// shape the screen reads. What the backend has (answers, mastery, the card deck, timed mock exams,
// cited chat) comes from it; flows it has no place for are kept on the device (store.ts); what it
// cannot do at all answers 501, which the screens already handle.
//
// How the two models meet:
//   học phần (module) g{n}   = đề mục n of QĐ 51
//   chủ đề (unit) vd{n}       = vấn đề n: a run of UNIT_LENGTH adaptive questions on it
//   bộ câu (practice set)     = adaptive items picked by the backend, graded one at a time
//   đề thi thử (exam form)    = a blueprint-allocated mock set of 10, 30 or 60 questions
//   thẻ (card)                = a deck card; a concept card is reviewed as a one-question set
import { liveChatCall } from "./chat";
import { fail, get, post, backend } from "./backend";
import {
  explain,
  feedbackOf,
  isoUtc,
  passageView,
  rememberSources,
  shortName,
  stemOf,
  toOptions,
  vnDay,
  type AnsweredItem,
} from "./shapes";
import {
  liveTransaction,
  nextId,
  readLive,
  record,
  type LiveState,
} from "./store";

const UNIT_LENGTH = 5;
const SESSION_PRACTICE = 5;
const WEAK_P = 0.6; // the backend's own line: below it a vấn đề is "weak"
const SOLID_ANSWERS = 3; // answers before a vấn đề can count as done
const INTERVAL_DAYS = [1, 3, 7, 21]; // the deck's schedule (yhdp/mcq/deck.py)
const MASTERED = INTERVAL_DAYS.length;
const RATING: Record<string, string> = {
  1: "again",
  2: "hard",
  3: "good",
  4: "good",
};
const FORMS = [
  { id: "de-10", title: "Đề ngắn 10 câu", size: 10 },
  { id: "de-30", title: "Đề thi thử 30 câu", size: 30 },
  { id: "de-60", title: "Đề thi thử 60 câu", size: 60 },
];
const DAY_S = 86400;

// ---- the blueprint and the learner model --------------------------------------------------

type Meta = {
  de_muc: { id: number; name: string }[];
  van_de: { id: number; de_muc: number; name: string }[];
  bloom: string[];
};
type Mastery = {
  van_de: {
    id: number;
    name: string;
    de_muc: number;
    items: number;
    p: number | null;
    answered: number;
    correct: number;
  }[];
  de_muc: {
    id: number;
    name: string;
    items: number;
    answered: number;
    correct: number;
  }[];
  due: number;
};

let meta: Promise<Meta> | null = null;
const blueprint = () =>
  (meta ??= get<Meta>("/meta").catch((e) => {
    meta = null;
    throw e;
  }));
const mastery = () => get<Mastery>("/mcq/mastery");

const unitDone = (v: Mastery["van_de"][number]) =>
  v.p !== null && v.p >= WEAK_P && v.answered >= SOLID_ANSWERS;

const vanDe = (m: Meta, unitId: string) =>
  m.van_de.find((x) => `vd${x.id}` === unitId) ??
  fail(404, "unit_not_found", "Không tìm thấy chủ đề.");

const focusReason = (focus?: { kind: string; p: number | null; n: number }) =>
  !focus || focus.kind === "new"
    ? "Vấn đề bạn chưa luyện: câu hỏi giúp ước lượng mức nắm vững."
    : focus.kind === "weak"
      ? `Vấn đề bạn còn yếu (ước lượng ${Math.round((focus.p ?? 0) * 100)}% sau ${focus.n} câu).`
      : "Duy trì vấn đề bạn đã khá vững.";

// ---- practice sets ------------------------------------------------------------------------

/** Distinct adaptive items. The backend picks one per call, weighted toward weak vấn đề. */
async function pickItems(filter: string, count: number) {
  const seen = new Map<number, any>();
  let tries = 0;
  while (seen.size < count && tries < count * 3) {
    const batch = Math.min(count - seen.size + 2, 10);
    const results = await Promise.all(
      Array.from({ length: batch }, () => get(`/mcq/practice${filter}`)),
    );
    tries += batch;
    let fresh = 0;
    for (const r of results)
      if (r.item && !seen.has(r.item.id)) {
        seen.set(r.item.id, r.item);
        fresh++;
      }
    if (fresh === 0) break; // nothing more in the bank for this filter
  }
  return [...seen.values()].slice(0, count);
}

// Where a set's questions came from, so a next round can be drawn from the same place: the whole
// bank, one đề mục, or a list of vấn đề (a topic quiz from Hỏi đáp).
type Scope = { de_muc: number | null; van_de: number[] | null };
const WHOLE_BANK: Scope = { de_muc: null, van_de: null };

function addSet(
  s: LiveState,
  fields: {
    source: string;
    topic: string;
    competency_code?: string;
    card_id?: number;
    scope?: Scope;
    reason?: string;
  },
  items: any[],
) {
  const id = nextId(s);
  s.practice[id] = {
    id,
    source: fields.source,
    competency_code: fields.competency_code ?? "",
    topic: fields.topic,
    card_id: fields.card_id ?? null,
    scope: fields.scope ?? WHOLE_BANK,
    completed: false,
    updated_at: new Date().toISOString(),
    items: items.map((item, n) => ({
      question_id: String(item.id),
      n: n + 1,
      stem: stemOf(item),
      options: toOptions(item.options),
      reason_vi: fields.reason ?? focusReason(item.focus),
      van_de: item.van_de,
      bloom: item.bloom,
      chosen: null,
      feedback: null,
    })),
  };
  return id;
}

function setView(s: LiveState, id: number) {
  const p =
    s.practice[id] ?? fail(404, "set_not_found", "Không tìm thấy bộ câu.");
  const { card_id: _card, scope: _scope, base_topic: _base, ...rest } = p;
  return {
    ...rest,
    total: p.items.length,
    answered: p.items.filter((i: any) => i.feedback !== null).length,
  };
}

async function answerInSet(id: number, body: any) {
  const p =
    readLive().practice[id] ??
    fail(404, "set_not_found", "Không tìm thấy bộ câu.");
  const item =
    p.items.find((i: any) => i.question_id === body.question_id) ??
    fail(404, "question_not_found", "Câu không thuộc bộ luyện.");
  if (item.feedback) return item.feedback;
  const r = await post<AnsweredItem>("/mcq/answer", {
    item_id: Number(body.question_id),
    chosen: body.chosen,
    seconds: body.time_ms ? body.time_ms / 1000 : null,
    card_id: p.card_id,
  });
  return liveTransaction((s) => {
    const { card_note: _note, ...f } = feedbackOf(s, r);
    const feedback = { ...f, next: { kind: "same_type" }, remediation: null };
    const stored = s.practice[id].items.find(
      (i: any) => i.question_id === body.question_id,
    );
    stored.chosen = body.chosen;
    stored.feedback = feedback;
    s.practice[id].updated_at = new Date().toISOString();
    record(
      s,
      p.card_id ? "cards" : "practice",
      p.topic,
      body.time_ms ? body.time_ms / 1000 : null,
    );
    return feedback;
  });
}

function completeSet(s: LiveState, id: number) {
  const p =
    s.practice[id] ?? fail(404, "set_not_found", "Không tìm thấy bộ câu.");
  const done = p.items.filter((i: any) => i.feedback);
  if (done.length < p.items.length)
    fail(409, "incomplete", "Hãy trả lời đủ câu trước khi hoàn thành.");
  p.completed = true;
  const cards = done.filter((i: any) => i.feedback.card_created).length;
  return {
    graded: {
      correct: done.filter((i: any) => i.feedback.correct).length,
      total: done.length,
    },
    mastery_updated: done.length ? { competencies: done.length } : null,
    cards_created: cards ? { n: cards } : null,
    tomorrow: null,
  };
}

// ---- the next round after a set ------------------------------------------------------------
//
// Difficulty is the learner's own: the bank's items are nearly all one Bloom level, so a harder
// round draws on the vấn đề they have mastered least (higher Bloom levels first), a lighter one on
// those they know best (lower levels first, fewer questions).

const NEXT_ROUND_VAN_DE = 3;
const LIGHTER_COUNT = 5;
const ROUND_REASON: Record<string, string> = {
  harder: "Vấn đề bạn cần luyện thêm nhiều nhất trong phạm vi này.",
  easier: "Vấn đề bạn đã nắm chắc hơn: củng cố trước khi tăng độ khó.",
};
const ROUND_SUFFIX: Record<string, string> = {
  harder: " · thử thách hơn",
  easier: " · nhẹ nhàng hơn",
};

/** Distinct items from these vấn đề, alternating between them. */
async function pickFromVanDe(ids: number[], count: number) {
  const per = Math.ceil(count / Math.max(ids.length, 1));
  const lists = await Promise.all(
    ids.map((v) => pickItems(`?van_de=${v}`, per)),
  );
  const out: any[] = [];
  for (let i = 0; out.length < count && lists.some((l) => i < l.length); i++)
    for (const l of lists)
      if (i < l.length && out.length < count) out.push(l[i]);
  return out;
}

async function nextRound(fromId: number, level: string) {
  if (!["same", "harder", "easier"].includes(level))
    fail(422, "invalid_level", "Mức độ không hợp lệ.");
  const prev =
    readLive().practice[fromId] ??
    fail(404, "set_not_found", "Không tìm thấy bộ câu.");
  // Sets made before scopes were kept: the vấn đề of their items.
  const scope: Scope = prev.scope ?? {
    de_muc: null,
    van_de: [
      ...new Set<number>(prev.items.map((i: any) => i.van_de).filter(Boolean)),
    ],
  };
  const baseTopic: string = prev.base_topic ?? prev.topic;
  const count =
    level === "easier"
      ? Math.min(LIGHTER_COUNT, prev.items.length)
      : prev.items.length;
  let items: any[];
  if (level === "same") {
    items = scope.van_de?.length
      ? await pickFromVanDe(scope.van_de, count)
      : await pickItems(scope.de_muc ? `?de_muc=${scope.de_muc}` : "", count);
  } else {
    const [meta, mt] = await Promise.all([blueprint(), mastery()]);
    const inScope = mt.van_de.filter((v) =>
      scope.van_de?.length
        ? scope.van_de.includes(v.id)
        : !scope.de_muc || v.de_muc === scope.de_muc,
    );
    // Answered vấn đề by estimated mastery; never-answered ones after them, their level unknown.
    const harder = level === "harder";
    const ranked = [...inScope].sort((a, b) =>
      a.p === null || b.p === null
        ? Number(a.p === null) - Number(b.p === null)
        : harder
          ? a.p - b.p
          : b.p - a.p,
    );
    const rank = (i: any) => meta.bloom.indexOf(i.bloom) * (harder ? -1 : 1);
    items = (
      await pickFromVanDe(
        ranked.slice(0, NEXT_ROUND_VAN_DE).map((v) => v.id),
        count * 2,
      )
    )
      .sort((a, b) => rank(a) - rank(b))
      .slice(0, count);
  }
  if (!items.length)
    fail(
      422,
      "no_questions",
      "Ngân hàng chưa có thêm câu hỏi trong phạm vi này.",
    );
  return liveTransaction((s) => {
    const id = addSet(
      s,
      {
        source: "learner",
        topic: baseTopic + (ROUND_SUFFIX[level] ?? ""),
        scope,
        reason: ROUND_REASON[level],
      },
      items,
    );
    s.practice[id].base_topic = baseTopic;
    return setView(s, id);
  });
}

// ---- units: a run of questions on one vấn đề ------------------------------------------------

function unitView(s: LiveState, id: string, topic: string) {
  const u = s.units[id];
  const entry = u.run[u.cursor];
  return {
    session_id: 0,
    unit_id: id,
    topic,
    position: u.cursor,
    total: u.total,
    done: u.cursor >= u.total,
    cards_created: u.cards_created,
    item: entry
      ? {
          unit_item_id: entry.unit_item_id,
          kind: "quiz",
          title: null,
          body: null,
          citations: null,
          reason: focusReason(entry.focus),
          question: {
            id: String(entry.item.id),
            stem: stemOf(entry.item),
            options: toOptions(entry.item.options),
          },
          chosen: entry.chosen,
          feedback: entry.feedback,
        }
      : null,
  };
}

async function unitNext(id: string) {
  const v = vanDe(await blueprint(), id);
  const today = vnDay(new Date());
  const before = readLive();
  const old = before.units[id];
  // A finished run starts again, except today's session unit on the day it was finished: the
  // session reads it as its step done.
  const restart =
    !old ||
    (old.finished_at &&
      !(vnDay(old.finished_at) === today && before.today?.unit_id === id));
  const need = restart || (!old.finished_at && !old.run[old.cursor]);
  const next = need ? await get(`/mcq/practice?van_de=${v.id}`) : null;
  return liveTransaction((s) => {
    if (restart)
      s.units[id] = {
        run: [],
        cursor: 0,
        total: UNIT_LENGTH,
        cards_created: 0,
        updated_at: new Date().toISOString(),
        finished_at: null,
      };
    const u = s.units[id];
    if (next && !u.run[u.cursor]) {
      const item = next.item;
      if (!item || u.run.some((e: any) => e.item.id === item.id)) {
        if (u.cursor === 0)
          fail(
            404,
            "no_questions",
            "Vấn đề này chưa có câu hỏi trong ngân hàng.",
          );
        u.total = u.cursor; // the bank has no more on this vấn đề
        u.finished_at = new Date().toISOString();
      } else {
        const { focus, ...rest } = item;
        u.run.push({
          unit_item_id: `${id}-${u.cursor}`,
          item: rest,
          focus,
          chosen: null,
          feedback: null,
        });
      }
    }
    return unitView(s, id, v.name);
  });
}

async function unitRespond(id: string, body: any) {
  const v = vanDe(await blueprint(), id);
  const u =
    readLive().units[id] ??
    fail(404, "unit_not_found", "Không tìm thấy chủ đề.");
  const entry = u.run[u.cursor];
  if (!entry || entry.unit_item_id !== body.unit_item_id)
    fail(409, "not_current_item", "Câu này không còn là câu hiện tại.");
  if (entry.feedback) return entry.feedback;
  const r = await post<AnsweredItem>("/mcq/answer", {
    item_id: entry.item.id,
    chosen: body.chosen,
    seconds: body.time_ms ? body.time_ms / 1000 : null,
  });
  return liveTransaction((s) => {
    const { card_note, ...f } = feedbackOf(s, r);
    const feedback = {
      ...f,
      remediation_inserted: false,
      remediation_note: card_note,
    };
    const unit = s.units[id];
    Object.assign(unit.run[unit.cursor], { chosen: body.chosen, feedback });
    unit.cards_created += Number(f.card_created);
    unit.updated_at = new Date().toISOString();
    record(s, "unit", v.name, body.time_ms ? body.time_ms / 1000 : null);
    return feedback;
  });
}

async function unitAdvance(id: string, body: any) {
  liveTransaction((s) => {
    const u =
      s.units[id] ?? fail(404, "unit_not_found", "Không tìm thấy chủ đề.");
    if (u.run[u.cursor]?.unit_item_id !== body.unit_item_id)
      fail(409, "not_current_item", "Bước học đã thay đổi.");
    u.cursor++;
    if (u.cursor >= u.total) u.finished_at = new Date().toISOString();
  });
  return unitNext(id);
}

// ---- cards --------------------------------------------------------------------------------

function preview(step: number) {
  const after = (s: number) =>
    s >= MASTERED ? 60 * DAY_S : s < 0 ? 600 : INTERVAL_DAYS[s] * DAY_S;
  return { 1: DAY_S, 2: after(step), 3: after(step + 1), 4: after(step + 1) };
}

async function dueCards() {
  const next = await get("/deck/next");
  if (!next.next) return { items: [], total_due: next.due };
  const n = next.next;
  const c = n.card;
  const card = liveTransaction((s) => {
    const base = {
      id: c.id,
      origin: c.origin === "chat" ? "Từ Hỏi đáp" : "Từ câu trả lời chưa chắc",
      module: c.title,
      preview: preview(c.step),
    };
    if (n.mode === "mcq") {
      // A concept card asks a different question on the same passage; the screens run it as a set.
      const reuse = s.practice[s.cardSets[c.id]];
      const setId =
        reuse &&
        !reuse.completed &&
        reuse.items[0].question_id === String(n.item.id)
          ? reuse.id
          : addSet(
              s,
              {
                source: "quiz_similar",
                topic: "Ôn thẻ: câu hỏi cùng nội dung",
                card_id: c.id,
              },
              [n.item],
            );
      s.cardSets[c.id] = setId;
      return {
        ...base,
        front: stemOf(n.item),
        back: "",
        citation: c.title,
        source_passage_id: "",
        practice_set_id: setId,
      };
    }
    const cites = rememberSources(s, n.sources);
    if (n.mode === "recall") s.recallItems[c.id] = n.item_id;
    else delete s.recallItems[c.id];
    return {
      ...base,
      front: n.front.replace(/\*\*/g, ""),
      back: n.back
        .replace(/\[S\d+\]/g, "")
        .replace(/\*\*/g, "")
        .trim(),
      citation: cites[0]?.document ?? c.title,
      source_passage_id: cites[0]?.passage_id ?? "",
      practice_set_id: null,
    };
  });
  return { items: [card], total_due: n.due };
}

async function reviewCard(id: number, body: any) {
  const item_id = readLive().recallItems[id] ?? null;
  const r = await post(`/deck/${id}/review`, {
    rating: RATING[body.rating] ?? "good",
    item_id,
  });
  const deck = await get("/deck");
  liveTransaction((s) => {
    delete s.recallItems[id];
    record(
      s,
      "cards",
      "Ôn thẻ",
      body.time_ms ? body.time_ms / 1000 : null,
      r.text,
    );
  });
  return {
    card_id: id,
    due_at: r.due ? isoUtc(r.due) : null,
    remaining_due: deck.due,
  };
}

// ---- exams --------------------------------------------------------------------------------

const formOf = (s: LiveState, set: { id: number; size: number }) =>
  FORMS.find((f) => f.id === s.attempts[set.id]?.form_id) ??
  FORMS.reduce((a, b) =>
    Math.abs(b.size - set.size) < Math.abs(a.size - set.size) ? b : a,
  );

const deadlineMs = (set: {
  started: string;
  minutes: number | null;
  items: unknown[];
}) =>
  Date.parse(isoUtc(set.started)) + (set.minutes ?? set.items.length) * 60000;

/** Mock sets, newest first; a topic set made in Hỏi đáp has a title and is not one. */
const mockSets = async () =>
  ((await get("/mcq/sets")).sets as any[]).filter((x) => x.title === null);

async function closeAttempt(set: any, auto: boolean) {
  const local = readLive().attempts[set.id] ?? { answers: {} };
  const answers = Object.fromEntries(
    set.items.map((i: any) => [
      String(i.id),
      local.answers[i.id]?.chosen ?? null,
    ]),
  );
  const seconds = Math.round(
    (Math.min(Date.now(), deadlineMs(set)) - Date.parse(isoUtc(set.started))) /
      1000,
  );
  const done = await post(`/mcq/sets/${set.id}/submit`, { answers, seconds });
  liveTransaction((s) => {
    s.attempts[set.id] = {
      ...(s.attempts[set.id] ?? { answers: {} }),
      auto_submitted: auto,
      duration_s: seconds,
      closed: true,
    };
    const r = done.report;
    record(
      s,
      "exam",
      formOf(s, done).title,
      seconds,
      `${r.correct}/${r.total} câu đúng`,
    );
  });
  return done;
}

/** A set as it is now: one whose time ran out while it was open is submitted with what was saved. */
async function currentSet(id: number) {
  let set = await get(`/mcq/sets/${id}`);
  const local = readLive().attempts[id];
  if (!set.submitted && local && Date.now() >= deadlineMs(set))
    set = await closeAttempt(set, true);
  return set;
}

async function openAttempts() {
  const s = readLive();
  const open = (await mockSets()).filter(
    (x) => !x.submitted && s.attempts[x.id] && !s.attempts[x.id].closed,
  );
  const sets = await Promise.all(open.map((x) => currentSet(x.id)));
  return sets.filter((x) => !x.submitted);
}

function attemptView(set: any) {
  const end = deadlineMs(set);
  const s = liveTransaction((t) => {
    if (!set.submitted)
      t.attempts[set.id] = {
        answers: {},
        ...t.attempts[set.id],
        deadline_ms: end,
      };
    return t;
  });
  const minutes = set.minutes ?? set.items.length;
  return {
    attempt_id: set.id,
    title: formOf(s, set).title,
    deadline_at: new Date(end).toISOString(),
    remaining_s: Math.max(0, Math.ceil((end - Date.now()) / 1000)),
    warning_s: Math.min(300, Math.floor((minutes * 60) / 4)),
    submitted: !!set.submitted,
    questions: set.items.map((i: any, n: number) => ({
      id: String(i.id),
      n: n + 1,
      stem: stemOf(i),
      options: toOptions(i.options),
    })),
    answers: s.attempts[set.id]?.answers ?? {},
  };
}

async function exams() {
  const open = await openAttempts();
  const sets = await mockSets();
  const s = readLive();
  return {
    items: FORMS.map((f) => {
      const history = sets
        .filter((x) => x.submitted && formOf(s, x).id === f.id && x.score)
        .map((x) => {
          const [score, total] = String(x.score).split("/").map(Number);
          return {
            attempt_id: x.id,
            submitted_at: isoUtc(x.submitted),
            duration_s: s.attempts[x.id]?.duration_s ?? 0,
            score,
            total,
            auto_submitted: s.attempts[x.id]?.auto_submitted ?? false,
          };
        });
      const running = open.find((x) => formOf(s, x).id === f.id);
      return {
        id: f.id,
        title: f.title,
        kind: "mock",
        n_questions: f.size,
        minutes: f.size,
        attempts_left: null,
        last: history[0] ?? null,
        open_attempt_id: running?.id ?? null,
        open_remaining_s: running
          ? Math.max(0, Math.ceil((deadlineMs(running) - Date.now()) / 1000))
          : null,
        history,
        plan: null,
      };
    }),
  };
}

async function startAttempt(formId: string, body: any) {
  const f =
    FORMS.find((x) => x.id === formId) ??
    fail(404, "form_not_found", "Không tìm thấy đề.");
  const running = (await openAttempts()).find(
    (x) => formOf(readLive(), x).id === f.id,
  );
  if (running && !body?.fresh) return attemptView(running);
  if (running) await closeAttempt(running, false);
  const set = await post("/mcq/sets", { size: f.size, timed: true });
  if (!set.items.length)
    fail(422, "no_questions", "Ngân hàng chưa có câu hỏi cho đề này.");
  liveTransaction((s) => {
    s.attempts[set.id] = { form_id: f.id, answers: {}, auto_submitted: false };
  });
  return attemptView(set);
}

/** Correct/total per đề mục, per Bloom level and per both, over answered items. */
function tally(
  items: { de_muc: number; bloom: string; correct: boolean }[],
  m: Meta,
) {
  const levels = m.bloom.map((label_vi, i) => ({
    level: i + 1,
    label_vi,
    correct: 0,
    total: 0,
  }));
  const groups = m.de_muc.map((d) => ({
    module_id: `g${d.id}`,
    name: shortName(d.id, d.name),
    correct: 0,
    total: 0,
    levels: levels.map((l) => ({ ...l })),
  }));
  for (const i of items) {
    const g = groups.find((x) => x.module_id === `g${i.de_muc}`);
    const at = m.bloom.indexOf(i.bloom);
    for (const stat of [g, levels[at], at >= 0 ? g?.levels[at] : undefined]) {
      if (!stat) continue;
      stat.total++;
      stat.correct += Number(i.correct);
    }
  }
  return {
    levels,
    specialties: groups.map(({ name, correct, total }) => ({
      name,
      correct,
      total,
    })),
    bloom_by_specialty: groups.map(({ module_id, name, levels }) => ({
      module_id,
      name,
      levels,
    })),
  };
}

async function results(set: any) {
  if (!set.submitted)
    fail(409, "attempt_open", "Cần nộp bài trước khi xem kết quả.");
  const m = await blueprint();
  const r = set.report;
  const names = new Map(m.van_de.map((v) => [v.id, v.name]));
  return liveTransaction((s) => {
    r.items.forEach((i: AnsweredItem) => explain(s, i));
    const wrong = new Map<number, number>();
    r.items.forEach(
      (i: AnsweredItem) =>
        !i.correct && wrong.set(i.van_de, (wrong.get(i.van_de) ?? 0) + 1),
    );
    const local = s.attempts[set.id];
    return {
      attempt_id: set.id,
      title: formOf(s, set).title,
      score: r.correct,
      total: r.total,
      wrong: r.total - r.correct - r.blank,
      blank: r.blank,
      submitted_at: isoUtc(set.submitted),
      duration_s: Math.round(r.seconds ?? 0),
      auto_submitted: local?.auto_submitted ?? false,
      new_cards: r.cards_added ?? 0,
      priority_top: [...wrong]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([v]) => names.get(v) ?? `Vấn đề ${v}`),
      priority_moved_up: [],
      items: r.items.map((i: AnsweredItem, n: number) => ({
        n: n + 1,
        question_id: String(i.id),
        topic: names.get(i.van_de) ?? `Vấn đề ${i.van_de}`,
        status: i.chosen === null ? "blank" : i.correct ? "ok" : "wrong",
      })),
      ...tally(r.items, m),
    };
  });
}

function reviewItem(set: any, questionId: string) {
  if (!set.submitted)
    fail(409, "attempt_open", "Không được xem đáp án khi đang thi.");
  const items: AnsweredItem[] = set.report.items;
  const at = items.findIndex((i) => String(i.id) === questionId);
  if (at < 0) fail(404, "question_not_in_attempt", "Câu không thuộc bài thi.");
  const r = items[at];
  return liveTransaction((s) => ({
    n: at + 1,
    total: items.length,
    question_id: questionId,
    stem: stemOf(r),
    options: toOptions(r.options).map((o) => ({
      ...o,
      is_correct: o.key === r.answer,
    })),
    chosen: r.chosen,
    ...explain(s, r),
  }));
}

// ---- progress -----------------------------------------------------------------------------

const daysTo = (date: string | undefined) =>
  date
    ? Math.max(0, Math.ceil((Date.parse(date) - Date.now()) / (DAY_S * 1000)))
    : undefined;

async function skills(scope: string) {
  const [m, mt, sets] = await Promise.all([blueprint(), mastery(), mockSets()]);
  const latest = sets
    .filter((x) => x.submitted)
    .slice(0, scope === "all" ? 30 : 3);
  const full = await Promise.all(latest.map((x) => get(`/mcq/sets/${x.id}`)));
  const s = readLive();
  const assessed = mt.van_de.filter((v) => v.answered > 0);
  return {
    days_to_exam: daysTo(s.prefs.exam_date),
    scope: scope === "all" ? "all" : "latest3",
    coverage: {
      assessed_topics: assessed.length,
      total_topics: m.van_de.length,
      modules: m.de_muc.map((d) => ({
        module_id: `g${d.id}`,
        short_name: shortName(d.id, d.name),
        topics_assessed: assessed.filter((v) => v.de_muc === d.id).length,
        topics_total: m.van_de.filter((v) => v.de_muc === d.id).length,
      })),
    },
    priorities: assessed
      .filter((v) => (v.p ?? 0) < WEAK_P)
      .map((v, i) => ({
        rank: i + 1,
        competency_code: `CI-${String(v.id).padStart(2, "0")}`,
        name: v.name,
        module_id: `g${v.de_muc}`,
        correct: v.correct,
        total: v.answered,
        weakest_vi: null,
      })),
    mock_scores: full.map((x) => ({
      attempt_id: x.id,
      title: formOf(s, x).title,
      submitted_at: isoUtc(x.submitted),
      score: x.report.correct,
      total: x.report.total,
    })),
    group_grid: null,
    ...tally(
      full.flatMap((x) => x.report.items),
      m,
    ),
  };
}

const minutesOf = (entries: LiveState["activity"]) =>
  Math.round(entries.reduce((t, a) => t + (a.seconds ?? 0), 0) / 60);

async function rhythm() {
  const deck = await get("/deck");
  const s = readLive();
  const now = new Date();
  const today = vnDay(now);
  const dayOf = (offset: number) =>
    vnDay(new Date(now.getTime() - offset * DAY_S * 1000));
  const weekday = (new Date(`${today}T12:00:00+07:00`).getUTCDay() + 6) % 7; // Monday = 0
  const thisWeek = new Set(
    Array.from({ length: weekday + 1 }, (_, i) => dayOf(i)),
  );
  const lastWeek = new Set(
    Array.from({ length: 7 }, (_, i) => dayOf(weekday + 1 + i)),
  );
  const on = (days: Set<string>) =>
    s.activity.filter((a) => days.has(vnDay(a.at)));
  const cards: any[] = deck.cards;
  const forecast = new Map<string, number>();
  for (const c of cards)
    if (c.due) {
      const day = vnDay(
        new Date(Math.max(Date.now(), Date.parse(isoUtc(c.due)))),
      );
      forecast.set(day, (forecast.get(day) ?? 0) + 1);
    }
  return {
    days_to_exam: daysTo(s.prefs.exam_date),
    week: {
      minutes: minutesOf(on(thisWeek)),
      previous_minutes: minutesOf(on(lastWeek)),
      study_days: new Set(on(thisWeek).map((a) => vnDay(a.at))).size,
      days_elapsed: weekday + 1,
    },
    heatmap: Array.from({ length: 56 }, (_, i) => dayOf(55 - i)).map(
      (date) => ({
        date,
        minutes: minutesOf(on(new Set([date]))),
      }),
    ),
    memory: {
      recall_rate: null,
      window_days: 30,
      reviews: cards.reduce((t, c) => t + c.reviews, 0),
      new: cards.filter((c) => c.reviews === 0 && c.step < MASTERED).length,
      learning: cards.filter((c) => c.reviews > 0 && c.step < MASTERED).length,
      mastered: deck.mastered,
      due_today: deck.due,
    },
    curve: [],
    recall_by_module: [],
    due_forecast: [...forecast]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, count]) => ({ date, count })),
    activity: s.activity
      .slice(-20)
      .reverse()
      .map((a) => ({
        kind: a.kind,
        title: a.title,
        occurred_at: a.at,
        minutes:
          a.seconds === null ? null : Math.max(1, Math.round(a.seconds / 60)),
        result_vi: a.result_vi,
      })),
  };
}

// ---- home and today's session --------------------------------------------------------------

/** The vấn đề to continue: in the learner's focus đề mục when set, the least mastered first. */
function pickUnit(mt: Mastery, focus: string[]) {
  const pool = mt.van_de.filter(
    (v) => !focus.length || focus.includes(`g${v.de_muc}`),
  );
  const order = (v: Mastery["van_de"][number]) =>
    (v.p === null ? 0.5 : v.p) + (unitDone(v) ? 1 : 0);
  return (
    [...(pool.length ? pool : mt.van_de)].sort(
      (a, b) => order(a) - order(b) || b.items - a.items,
    )[0] ?? null
  );
}

let planning: Promise<void> | null = null;

/** Today's practice set and unit, chosen once a day. */
function planToday(mt: Mastery) {
  return (planning ??= (async () => {
    const today = vnDay(new Date());
    if (readLive().today?.date === today) return;
    const items = await pickItems("", SESSION_PRACTICE);
    const unit = pickUnit(mt, readLive().prefs.focus_module_ids ?? []);
    liveTransaction((s) => {
      if (s.today?.date === today) return;
      s.today = {
        date: today,
        practice_set_id: items.length
          ? addSet(
              s,
              { source: "session", topic: "Luyện điểm yếu hôm nay" },
              items,
            )
          : null,
        unit_id: unit ? `vd${unit.id}` : null,
      };
    });
  })().finally(() => {
    planning = null;
  }));
}

async function sessionToday() {
  const mt = await mastery();
  await planToday(mt);
  const s = readLive();
  const t = s.today!;
  const today = t.date;
  const steps = [];
  const reviewed = s.activity.filter(
    (a) => a.kind === "cards" && vnDay(a.at) === today,
  ).length;
  if (mt.due > 0 || reviewed > 0)
    steps.push({
      kind: "cards",
      count: mt.due || reviewed,
      minutes: Math.max(1, Math.ceil(mt.due / 2)),
      reason_vi: "Thẻ đến hạn theo lịch ôn 1 – 3 – 7 – 21 ngày.",
      done: mt.due === 0,
      practice_set_id: null,
      unit_id: null,
    });
  const p = t.practice_set_id ? s.practice[t.practice_set_id] : null;
  if (p)
    steps.push({
      kind: "practice",
      count: p.items.length,
      minutes: Math.ceil(p.items.length * 1.5),
      reason_vi: "Câu hỏi chọn theo vấn đề bạn còn yếu và trọng số đề thi.",
      done: p.completed,
      practice_set_id: p.id,
      unit_id: null,
    });
  const v = t.unit_id ? mt.van_de.find((x) => `vd${x.id}` === t.unit_id) : null;
  if (v) {
    const u = s.units[t.unit_id!];
    steps.push({
      kind: "continue",
      count: UNIT_LENGTH,
      minutes: UNIT_LENGTH * 2,
      reason_vi: `Vấn đề ${v.id}: ${v.name}.`,
      done: !!u?.finished_at && vnDay(u.finished_at) === today,
      practice_set_id: null,
      unit_id: t.unit_id,
    });
  }
  return {
    local_date: today,
    steps,
    total_minutes: steps
      .filter((x) => !x.done)
      .reduce((n, x) => n + x.minutes, 0),
  };
}

async function home() {
  const [mt, m, open] = await Promise.all([
    mastery(),
    blueprint(),
    openAttempts(),
  ]);
  const s = readLive();
  const running = open[0];
  const form = running ? formOf(s, running) : FORMS[1];
  const weak = mt.van_de.filter((v) => v.answered > 0 && (v.p ?? 0) < WEAK_P);
  const start = pickUnit(mt, s.prefs.focus_module_ids ?? []);
  const suggestions = [];
  if (mt.due > 0)
    suggestions.push({
      kind: "cards",
      text_vi: `${mt.due} thẻ ôn đang đến hạn.`,
      action: { label_vi: "Ôn thẻ", target: "cards", id: null },
    });
  if (weak[0])
    suggestions.push({
      kind: "weak",
      text_vi: `Luyện thêm “${weak[0].name}”: mới đúng ${weak[0].correct}/${weak[0].answered} câu.`,
      action: { label_vi: "Luyện ngay", target: "unit", id: `vd${weak[0].id}` },
    });
  else if (start)
    suggestions.push({
      kind: "continue",
      text_vi: `Bắt đầu với “${start.name}”.`,
      action: { label_vi: "Học ngay", target: "unit", id: `vd${start.id}` },
    });
  const byUnit = new Map(m.van_de.map((v) => [`vd${v.id}`, v]));
  return {
    name: s.prefs.display_name ?? "",
    days_to_exam: daysTo(s.prefs.exam_date) ?? null,
    resume: resumeItem(s, m, running),
    tutor_topics: tutorTopics(s, mt).slice(0, 2),
    quick_review_count: mt.due,
    quick_review_note_vi: mt.due ? "Theo lịch ôn của bạn" : null,
    due_cards: mt.due,
    next_mock: {
      form_id: form.id,
      title: form.title,
      n_questions: form.size,
      minutes: form.size,
      open_attempt_id: running?.id ?? null,
    },
    tutor_suggestions: suggestions,
    recent: Object.entries(s.units)
      .filter(([id]) => byUnit.has(id))
      .sort(([, a]: any, [, b]: any) =>
        b.updated_at.localeCompare(a.updated_at),
      )
      .slice(0, 3)
      .map(([id, u]: any) => {
        const v = byUnit.get(id)!;
        return {
          kind: "unit",
          id,
          title: v.name,
          subtitle_vi: shortName(v.de_muc),
          progress: u.total ? u.cursor / u.total : 0,
        };
      }),
  };
}

// ---- what to resume, and what to ask the tutor --------------------------------------------

/** The one thing to pick up again on Home: an exam still running, else whichever unit run,
 *  practice set or conversation was touched last. Today's session has its own card. */
function resumeItem(s: LiveState, m: Meta, running: any) {
  if (running) {
    const left = Math.max(
      0,
      Math.ceil((deadlineMs(running) - Date.now()) / 60000),
    );
    return {
      kind: "exam",
      id: running.id,
      title: formOf(s, running).title,
      subtitle_vi: `Bài thi đang làm · còn ${left} phút`,
      progress: null,
      path: `/thi-thu/lam-bai/${running.id}`,
    };
  }
  const names = new Map(m.van_de.map((v) => [`vd${v.id}`, v.name]));
  const todaySet = s.today?.practice_set_id;
  const candidates = [
    ...Object.entries(s.units)
      .filter(
        ([id, u]: [string, any]) =>
          names.has(id) && !u.finished_at && u.cursor > 0,
      )
      .map(([id, u]: [string, any]) => ({
        at: u.updated_at,
        kind: "unit",
        id,
        title: names.get(id)!,
        subtitle_vi: `Chủ đề · ${u.cursor}/${u.total} câu`,
        progress: u.total ? u.cursor / u.total : null,
        path: `/luyen-tap/${id}`,
      })),
    ...Object.values(s.practice)
      .filter(
        (p: any) =>
          !p.completed &&
          !p.card_id &&
          p.id !== todaySet &&
          p.updated_at &&
          p.items.some((i: any) => i.feedback),
      )
      .map((p: any) => {
        const done = p.items.filter((i: any) => i.feedback).length;
        return {
          at: p.updated_at,
          kind: "practice_set",
          id: p.id,
          title: p.topic,
          subtitle_vi: `Bộ câu luyện · ${done}/${p.items.length} câu`,
          progress: done / p.items.length,
          path: `/luyen-tap/bo-cau/${p.id}`,
        };
      }),
    ...s.chats
      .filter((c) => c.messages.length > 0)
      .map((c) => ({
        at: c.updated_at,
        kind: "chat",
        id: c.id,
        title: c.title,
        subtitle_vi: "Hỏi đáp với gia sư",
        progress: null,
        path: null, // opened in the tutor popup
      })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  if (!candidates.length) return null;
  const { at: _at, ...item } = candidates[0];
  return item;
}

/** What to ask the tutor about next, from the learner's own record, each with why and the move
 *  that fits: the vấn đề they keep missing (compare what is confused), the weakest one (explain),
 *  one in their focus not practised yet (a worked case), one they hold well (quiz to keep it). */
function tutorTopics(s: LiveState, mt: Mastery) {
  const missed = new Map<number, number>();
  const miss = (vanDe: number | undefined, feedback: any) => {
    if (vanDe && feedback && !feedback.correct)
      missed.set(vanDe, (missed.get(vanDe) ?? 0) + 1);
  };
  for (const u of Object.values(s.units) as any[])
    for (const e of u.run) miss(e.item.van_de, e.feedback);
  for (const p of Object.values(s.practice) as any[])
    for (const i of p.items) miss(i.van_de, i.feedback);
  const byId = new Map(mt.van_de.map((v) => [v.id, v]));
  const focus: string[] = s.prefs.focus_module_ids ?? [];
  const inFocus = (v: Mastery["van_de"][number]) =>
    !focus.length || focus.includes(`g${v.de_muc}`);
  const used = new Set<number>();
  const topics: { reason_vi: string; label_vi: string; prompt: string }[] = [];
  const add = (
    v: Mastery["van_de"][number] | undefined,
    topic: (typeof topics)[number],
  ) => {
    if (!v || used.has(v.id)) return;
    used.add(v.id);
    topics.push(topic);
  };
  const mostMissed = [...missed]
    .filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1])[0];
  if (mostMissed) {
    const v = byId.get(mostMissed[0]);
    add(v, {
      reason_vi: `Gần đây bạn trả lời chưa đúng ${mostMissed[1]} câu về “${v?.name}”.`,
      label_vi: "So sánh, phân biệt",
      prompt: `So sánh, phân biệt các điểm dễ nhầm về ${v?.name}`,
    });
  }
  const weakest = mt.van_de
    .filter(
      (v) => v.answered >= 2 && v.p !== null && v.p < WEAK_P && !used.has(v.id),
    )
    .sort((a, b) => a.p! - b.p!)[0];
  add(weakest, {
    reason_vi: `“${weakest?.name}”: mới đúng ${weakest?.correct}/${weakest?.answered} câu.`,
    label_vi: "Giải thích",
    prompt: `Giải thích những điểm chính về ${weakest?.name}`,
  });
  const fresh = mt.van_de.find(
    (v) => v.answered === 0 && inFocus(v) && !used.has(v.id),
  );
  add(fresh, {
    reason_vi: `Bạn chưa luyện “${fresh?.name}”.`,
    label_vi: "Ca lâm sàng",
    prompt: `Cho mình một ca lâm sàng về ${fresh?.name}`,
  });
  const solid = mt.van_de.find((v) => unitDone(v) && !used.has(v.id));
  add(solid, {
    reason_vi: `Bạn đã khá vững “${solid?.name}”: tự kiểm tra để giữ kiến thức.`,
    label_vi: "Kiểm tra mình",
    prompt: `Kiểm tra mình về ${solid?.name}`,
  });
  return topics;
}

// ---- profile ------------------------------------------------------------------------------

const PROFILE_FIELDS = [
  "display_name",
  "audience",
  "organisation",
  "focus_module_ids",
  "exam_date",
  "target_retention",
  "new_cards_per_day",
  "max_reviews_per_day",
  "diagnostic_prompt_dismissed",
];

async function me() {
  const who = await get("/me");
  return liveTransaction((s) => {
    s.prefs.display_name ??= who.username;
    const p = s.prefs;
    return {
      pseudonym_id: who.username,
      display_name: p.display_name,
      audience: p.audience ?? "student",
      organisation: p.organisation ?? null,
      focus_module_ids: p.focus_module_ids ?? [],
      exam_date: p.exam_date ?? "",
      target_retention: p.target_retention ?? 0.9,
      new_cards_per_day: p.new_cards_per_day ?? 20,
      max_reviews_per_day: p.max_reviews_per_day ?? 200,
      diagnostic_prompt_dismissed: p.diagnostic_prompt_dismissed ?? false,
      // The backend asks no consent; the learner signed in to their own study account.
      consent: {
        version: "live",
        service_given_at: p.consent_at,
        research_given_at: null,
      },
    };
  });
}

const CONSENT_TEXT = {
  version: "live",
  service_text_vi:
    "Câu trả lời, thẻ ôn và bài thi thử của bạn được lưu trên máy chủ ôn tập để tính mức nắm vững và lịch ôn.",
  research_text_vi: "Máy chủ này không dùng dữ liệu của bạn cho nghiên cứu.",
};

// ---- the router ---------------------------------------------------------------------------

const inflight = new Map<string, Promise<unknown>>();

export async function liveCall(
  method: string,
  path: string,
  body: any,
  key?: string,
) {
  if (!key) return liveRequest(method, path, body);
  const scope = `${method}:${path}:${key}`;
  const cached = readLive().idempotency[scope];
  if (cached !== undefined) return cached;
  if (inflight.has(scope)) return inflight.get(scope);
  const run = liveRequest(method, path, body)
    .then((result) => {
      liveTransaction((s) => {
        s.idempotency[scope] = result;
      });
      return result;
    })
    .finally(() => inflight.delete(scope));
  inflight.set(scope, run);
  return run;
}

async function liveRequest(
  method: string,
  path: string,
  body: any = {},
): Promise<unknown> {
  const url = new URL(path, "http://live.local");
  const p = url.pathname;
  const q = url.searchParams;
  let m: RegExpExecArray | null;

  if (p === "/auth/logout") return { ok: true };
  if (p === "/me" && method === "GET") return me();
  if (p === "/me" && method === "PATCH") {
    liveTransaction((s) => {
      for (const k of PROFILE_FIELDS) if (k in body) s.prefs[k] = body[k];
    });
    return me();
  }
  if (p === "/me/data") {
    const [profile, deck, sets, mt] = await Promise.all([
      me(),
      get("/deck"),
      get("/mcq/sets"),
      mastery(),
    ]);
    return {
      exported_at: new Date().toISOString(),
      profile,
      cards: deck.cards,
      attempts: sets.sets,
      mastery: mt,
    };
  }
  if (p === "/consent/current") return CONSENT_TEXT;
  if (p === "/consent" && method === "POST") {
    liveTransaction((s) => {
      s.prefs.consent_at = new Date().toISOString();
    });
    return (await me()).consent;
  }

  if (p === "/modules") {
    const [meta, mt] = await Promise.all([blueprint(), mastery()]);
    const fold = (t: string) =>
      t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/đ/g, "d");
    const items = meta.de_muc.map((d) => {
      const units = mt.van_de.filter((v) => v.de_muc === d.id);
      const done = units.filter(unitDone).length;
      return {
        id: `g${d.id}`,
        name: d.name,
        short_name: shortName(d.id, d.name),
        core_issue_group: d.id,
        coming_soon: units.length === 0,
        units_total: units.length,
        units_done: done,
        topics_total: meta.van_de.filter((v) => v.de_muc === d.id).length,
        status:
          units.length && done === units.length
            ? "done"
            : units.some((v) => v.answered > 0)
              ? "in_progress"
              : "not_started",
        issues: units.map((v) => v.id),
      };
    });
    return {
      items: items
        .filter(
          (x) =>
            (!q.get("q") ||
              fold(`${x.name} ${x.short_name}`).includes(fold(q.get("q")!))) &&
            (!q.get("status") || x.status === q.get("status")) &&
            (!q.get("group") ||
              x.core_issue_group === Number(q.get("group"))) &&
            (!q.get("core_issue") ||
              x.issues.includes(Number(q.get("core_issue")))),
        )
        .map(({ status: _s, issues: _i, ...x }) => x),
    };
  }
  if ((m = /^\/modules\/g(\d+)$/.exec(p))) {
    const [meta, mt] = await Promise.all([blueprint(), mastery()]);
    const d =
      meta.de_muc.find((x) => x.id === Number(m![1])) ??
      fail(404, "module_not_found", "Không tìm thấy học phần.");
    return {
      id: `g${d.id}`,
      name: d.name,
      short_name: shortName(d.id, d.name),
      units: mt.van_de
        .filter((v) => v.de_muc === d.id)
        .sort((a, b) => a.id - b.id)
        .map((v) => ({ id: `vd${v.id}`, topic: v.name, done: unitDone(v) })),
    };
  }
  if ((m = /^\/units\/([^/]+)\/(next|responses|advance)$/.exec(p))) {
    if (m[2] === "responses") return unitRespond(m[1], body);
    if (m[2] === "advance") return unitAdvance(m[1], body);
    return unitNext(m[1]);
  }

  if (p === "/home") return home();
  if (p === "/session/today") return sessionToday();
  if (
    (m =
      /^\/(?:practice-sets\/(\d+)|session\/today\/practice)(?:\/(responses|complete))?$/.exec(
        p,
      ))
  ) {
    if (!m[1]) await sessionToday();
    const id = m[1] ? Number(m[1]) : readLive().today?.practice_set_id;
    if (!id) fail(404, "no_practice", "Hôm nay chưa có bộ luyện.");
    if (m[2] === "responses") return answerInSet(id!, body);
    if (m[2] === "complete") return liveTransaction((s) => completeSet(s, id!));
    return setView(readLive(), id!);
  }
  if (p === "/practice-sets" && method === "POST") {
    if (body.from_set)
      return nextRound(Number(body.from_set), String(body.level));
    const count = Number(body.count);
    if (![5, 10, 20, 30, 60].includes(count))
      fail(422, "invalid_count", "Chọn 10, 20, 30 hoặc 60 câu.");
    const g = /^g(\d+)$/.exec(body.module_id ?? "");
    const items = await pickItems(g ? `?de_muc=${g[1]}` : "", count);
    if (!items.length)
      fail(422, "no_questions", "Nhóm này chưa có câu hỏi trong ngân hàng.");
    return liveTransaction((s) =>
      setView(
        s,
        addSet(
          s,
          {
            source: "learner",
            topic: g ? shortName(Number(g[1])) : "Ôn tập tổng hợp",
            scope: { de_muc: g ? Number(g[1]) : null, van_de: null },
          },
          items,
        ),
      ),
    );
  }

  if (p === "/cards/due") return dueCards();
  if (p === "/decks") {
    const deck = await get("/deck");
    const cards: any[] = deck.cards;
    return {
      items: [
        {
          module_id: "all",
          name: "Tất cả thẻ ôn tập",
          short_name: "Tất cả thẻ",
          new: cards.filter((c) => c.reviews === 0 && c.step < MASTERED).length,
          learning: cards.filter((c) => c.reviews > 0 && c.step < MASTERED)
            .length,
          due: deck.due,
        },
      ],
    };
  }
  if ((m = /^\/cards\/(\d+)\/reviews$/.exec(p)))
    return reviewCard(Number(m[1]), body);
  if ((m = /^\/cards\/(\d+)$/.exec(p)) && method === "PATCH") {
    // The deck has no suspended state: taking a card out of the queue deletes it.
    if (body.suspended) await backend("DELETE", `/deck/${m[1]}`);
    return { ok: true };
  }

  if (p === "/exams") return exams();
  if ((m = /^\/exams\/([^/]+)\/attempts$/.exec(p)))
    return startAttempt(m[1], body);
  if (
    (m =
      /^\/attempts\/(\d+)(?:\/(answers|submit|results|items)(?:\/([^/]+))?)?$/.exec(
        p,
      ))
  ) {
    const id = Number(m[1]);
    if (m[2] === "answers") {
      const local =
        readLive().attempts[id] ??
        fail(404, "attempt_not_found", "Không tìm thấy bài làm.");
      if (
        local.closed ||
        (local.deadline_ms && Date.now() >= local.deadline_ms)
      )
        fail(409, "attempt_closed", "Bài thi đã hết giờ hoặc đã được nộp.");
      liveTransaction((s) => {
        s.attempts[id].answers[m![3]] = {
          chosen: body.chosen ?? null,
          flagged: !!body.flagged,
        };
      });
      return { ok: true };
    }
    const set = await currentSet(id);
    if (m[2] === "submit")
      return results(set.submitted ? set : await closeAttempt(set, false));
    if (m[2] === "results") return results(set);
    if (m[2] === "items") return reviewItem(set, m[3]);
    return attemptView(set);
  }

  if (p === "/progress/skills") return skills(q.get("scope") ?? "latest3");
  if (p === "/progress/rhythm") return rhythm();

  // Chunk ids hold "#" and "/" ("qd5642#benh-thuong-han/4/4.2#c01") and the screens put them in
  // the path as they are, so the id is read from the raw path: URL parsing ends it at the "#".
  if ((m = /^\/passages\/(.+)$/.exec(path))) {
    let id = m[1];
    try {
      id = decodeURIComponent(id);
    } catch {
      // not encoded
    }
    const passage =
      readLive().passages[id] ??
      fail(
        404,
        "passage_not_found",
        "Đoạn nguồn chưa có trên thiết bị này. Mở lại câu hỏi hoặc câu trả lời để xem nguồn.",
      );
    return passageView(id, passage);
  }

  if (p === "/reports" && method === "POST") {
    if (body.target_type !== "question" || !/^\d+$/.test(body.target_id))
      fail(
        501,
        "not_implemented",
        "Máy chủ hiện chỉ nhận phản ánh về câu hỏi.",
      );
    await post(`/mcq/items/${body.target_id}/flag`, {
      reason: [body.reason, body.note].filter(Boolean).join(": "),
    });
    return { id: Number(body.target_id) };
  }

  if (p === "/chat/recommendations")
    return { items: tutorTopics(readLive(), await mastery()) };

  const chat = await liveChatCall(method, p, body);
  if (chat !== undefined) return chat;

  return fail(
    501,
    "not_implemented",
    "Chức năng này chưa có trên máy chủ ôn tập.",
  );
}
