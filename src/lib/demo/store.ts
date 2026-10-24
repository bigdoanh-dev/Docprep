import { groupForQuestion, summarizeAnswers } from "../learningAnalytics";
import { getActor } from "../../app/identity";
import rawExamples from "./examples.json";
import rawSeed from "./seed.json";
// Isolated browser demonstration. This module never calls a model or writes to the backend.
export const seed = rawSeed as any;
export const examples = rawExamples as Record<string, any>;
const KEY = "yhdp.demo.v2";
const clone = <T>(v: T): T => structuredClone(v);
export const now = () => new Date().toISOString();
export const day = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(
    new Date(),
  );
export const passages = seed.documents.flatMap((d: any) =>
  d.passages.map((p: any) => ({
    ...p,
    document: d.title,
    excerpt: p.text,
    demo_label: d.demo_label,
    validity_note: null,
    article: null,
  })),
);
export function citations(ids: string[]) {
  return ids.map((id, i) => {
    const p = passages.find((x: any) => x.id === id);
    return {
      n: i + 1,
      passage_id: id,
      document: p?.document ?? "Nguồn minh họa",
      chapter: p?.chapter ?? null,
      section: p?.section ?? null,
      page: p?.page ?? null,
      article: null,
    };
  });
}
const question = (id: string) => seed.questions.find((q: any) => q.id === id);
function initial() {
  const cardIds = ["q-dt-01", "q-dt-02", "q-dt-04"];
  return {
    version: 2,
    me: {
      ...clone(examples.Me),
      display_name: "Nguyễn Thu Hà",
      focus_module_ids: ["g1"],
      diagnostic_prompt_dismissed: false,
      consent: {
        version: "2026-10",
        service_given_at: null,
        research_given_at: null,
      },
    },
    units: {} as Record<string, any>,
    responses: [] as any[],
    cards: cardIds.map((id, i) => cardFromQuestion(id, i + 1)),
    attempts: [] as any[],
    practice: {} as Record<string, any>,
    chats: [] as any[],
    reports: [] as any[],
    suggestions: [] as any[],
    nextId: 100,
    tomorrow: null as any,
    studyPlan: null as any,
    classes: [
      {
        id: "lop-01",
        name: "YHDP năm cuối — lớp A",
        school: "CSĐT A",
        learners: 48,
        teacher: "Giảng viên minh họa",
      },
    ],
    schedules: [] as any[],
    review: seed.questions.slice(0, 4).map((q: any, i: number) => ({
      id: q.id,
      type: "question",
      version: 1,
      status: i === 3 ? "in_review_r2" : "in_review_r1",
      ai_assisted: true,
      competency_code: q.competency_code,
      stem: q.stem,
      options: q.options.map((o: any) => ({ ...o, is_correct: o.correct })),
      explanation: q.explanation,
      passages: q.sources.map((id: string) =>
        passages.find((p: any) => p.id === id),
      ),
      core_issue_id: null,
      bloom_level: q.bloom_level,
      difficulty_label: q.difficulty,
      decisions:
        i === 3
          ? [
              {
                round: 1,
                decision: "pass",
                comment: "Quyết định minh họa vòng 1",
                reviewer: "demo-reviewer-1",
                created_at: now(),
              },
            ]
          : [],
      transitions: [],
    })),
  };
}
export function readStore(): any {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (value?.version === 2) return value;
  } catch {
    /* invalid local fixture is reset */
  }
  const s = initial();
  writeStore(s);
  return s;
}
export function writeStore(s: any) {
  localStorage.setItem(KEY, JSON.stringify(s));
  window.dispatchEvent(new Event("yhdp-demo-change"));
}
export function resetDemo() {
  localStorage.removeItem(KEY);
  readStore();
}
export function demoTransaction<T>(run: (s: any) => T): T {
  const s = readStore();
  const value = run(s);
  writeStore(s);
  return clone(value);
}
function cardFromQuestion(id: string, cardId: number) {
  const q = question(id);
  return {
    id: cardId,
    front: q.stem,
    back: q.explanation,
    citation: `${citations(q.sources)[0].document}, trang ${citations(q.sources)[0].page}`,
    source_passage_id: q.sources[0],
    origin: "Từ kết quả minh họa",
    module: "Sức khỏe quần thể và dự phòng",
    preview: { 1: 60, 2: 600, 3: 86400, 4: 345600 },
    due_at: now(),
    suspended: false,
    reviews: 0,
    source_question_id: id,
  };
}
export class DemoError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}
const inflight = new Map<string, Promise<unknown>>();
export async function demoCall(
  method: string,
  path: string,
  body: unknown,
  key?: string,
): Promise<unknown> {
  if (!key) return demoRequest(method, path, body);
  const scope = `${getActor()?.id}:${method}:${path}:${key}`,
    cached = readStore().idempotency?.[scope];
  if (cached !== undefined) return clone(cached);
  if (inflight.has(scope)) return inflight.get(scope);
  const run = demoRequest(method, path, body)
    .then((result) => {
      demoTransaction((s) => {
        s.idempotency ??= {};
        s.idempotency[scope] = result;
        return result;
      });
      return result;
    })
    .finally(() => inflight.delete(scope));
  inflight.set(scope, run);
  return run;
}
const fail = (status: number, code: string, message: string): never => {
  throw new DemoError(status, code, message);
};
function grade(s: any, q: any, chosen: string, context: string) {
  const previous = s.responses.find(
    (r: any) => r.context === context && r.question_id === q.id,
  );
  if (previous) return previous.feedback;
  if (!q.options.some((o: any) => o.key === chosen))
    fail(422, "unknown_option", "Phương án không hợp lệ.");
  const correct = q.options.find((o: any) => o.correct).key === chosen;
  let created = false;
  if (!correct && !s.cards.some((c: any) => c.source_question_id === q.id)) {
    s.cards.push(cardFromQuestion(q.id, ++s.nextId));
    created = true;
  }
  const f = {
    correct,
    correct_key: q.options.find((o: any) => o.correct).key,
    explanation: q.explanation,
    rationales: Object.fromEntries(
      q.options.map((o: any) => [o.key, o.rationale]),
    ),
    citations: citations(q.sources),
    remediation_inserted: false,
    remediation_note: null,
    card_created: created,
    next: { kind: "same_type" },
    remediation: null,
  };
  s.responses.push({
    question_id: q.id,
    chosen,
    correct,
    context,
    created_at: now(),
    feedback: f,
  });
  return f;
}
function unitState(s: any, id: string) {
  const u = seed.modules
    .flatMap((m: any) => m.units)
    .find((u: any) => u.id === id);
  if (!u) fail(404, "unit_not_found", "Không tìm thấy chủ đề.");
  s.units[id] ??= {
    cursor: 0,
    queue: clone(u.items.filter((i: any) => i.kind !== "remediation")),
    cards_created: 0,
  };
  return { u, state: s.units[id] };
}
function unitView(s: any, id: string) {
  const { u, state } = unitState(s, id);
  const raw = state.queue[state.cursor];
  const q = raw?.question ? question(raw.question) : null;
  const r =
    q &&
    s.responses.find(
      (r: any) =>
        r.question_id === q.id && r.context === `unit:${id}:${raw.id}`,
    );
  return {
    session_id: 1,
    unit_id: id,
    topic: u.topic,
    position: state.cursor,
    total: state.queue.length,
    done: state.cursor >= state.queue.length,
    cards_created: state.cards_created,
    item: raw
      ? {
          unit_item_id: raw.id,
          kind: raw.kind,
          title: raw.content?.title ?? null,
          body: raw.content?.body ?? null,
          citations: citations(raw.content?.sources ?? q?.sources ?? []),
          reason: raw.note ?? null,
          question: q
            ? {
                id: q.id,
                stem: q.stem,
                options: q.options.map(({ key, text }: any) => ({ key, text })),
              }
            : null,
          chosen: r?.chosen ?? null,
          feedback: r?.feedback ?? null,
        }
      : null,
  };
}
function practice(s: any, id: number) {
  s.practice[id] ??= {
    id,
    source: "session",
    competency_code: "FND",
    topic: "Đo lường tần suất bệnh",
    completed: false,
    items: seed.questions.slice(0, 6).map((q: any, n: number) => ({
      question_id: q.id,
      n: n + 1,
      stem: q.stem,
      options: q.options.map(({ key, text }: any) => ({ key, text })),
      reason_vi: "Câu hỏi cùng chủ đề đang ôn. Dữ liệu minh họa.",
      chosen: null,
      feedback: null,
    })),
  };
  const p = s.practice[id];
  return {
    ...p,
    total: p.items.length,
    answered: p.items.filter((i: any) => i.chosen !== null).length,
  };
}
function sessionToday(s: any) {
  const due = s.cards.filter(
    (c: any) => !c.suspended && new Date(c.due_at).getTime() <= Date.now(),
  ).length;
  const p = practice(s, 31);
  const stepUnit = unitView(s, "u-dt-01");
  const steps = [
    {
      kind: "cards",
      count: due,
      minutes: Math.ceil(due / 2),
      reason_vi: "Thẻ đến hạn được tính từ lịch ôn minh họa.",
      done: due === 0,
      practice_set_id: null,
      unit_id: null,
    },
    {
      kind: "practice",
      count: p.total,
      minutes: 8,
      reason_vi: "Ôn kiến thức đo lường tần suất bệnh bằng câu mẫu.",
      done: p.completed,
      practice_set_id: 31,
      unit_id: null,
    },
    {
      kind: "continue",
      count: stepUnit.total,
      minutes: 6,
      reason_vi: "Tiếp tục chủ đề đang ưu tiên.",
      done: stepUnit.done,
      practice_set_id: null,
      unit_id: "u-dt-01",
    },
  ];
  return {
    local_date: day(),
    steps,
    total_minutes: steps
      .filter((v) => !v.done)
      .reduce((t, v) => t + v.minutes, 0),
  };
}
function forms(s: any) {
  return [
    {
      id: "diagnostic-demo",
      title: "Bài đánh giá đầu vào minh họa",
      kind: "diagnostic",
      n_questions: 5,
    },
    {
      id: "mock-demo",
      title: "Đề thi thử minh họa",
      kind: "demo_short",
      n_questions: 10,
    },
    {
      id: "assembled-demo",
      title: "Đề ôn tự ráp minh họa",
      kind: "assembled",
      n_questions: 8,
    },
  ].map((f) => {
    const history = s.attempts
      .filter((a: any) => a.form_id === f.id && a.submitted_at)
      .map((a: any) => ({
        attempt_id: a.attempt_id,
        submitted_at: a.submitted_at,
        duration_s: a.results.duration_s,
        score: a.results.score,
        total: a.questions.length,
      }));
    const running = s.attempts.find(
      (a: any) => a.form_id === f.id && !a.submitted_at,
    );
    return {
      ...f,
      minutes: Math.ceil((f.n_questions * 75) / 60),
      attempts_left: 5 - history.length,
      last: history[0] ?? null,
      open_attempt_id: running?.attempt_id ?? null,
      open_remaining_s: running
        ? Math.max(
            0,
            Math.ceil((Date.parse(running.deadline_at) - Date.now()) / 1000),
          )
        : null,
      history,
      plan:
        f.kind === "assembled"
          ? {
              composition: { new: 4, wrong: 2, review: 2 },
              topics: [{ name: "Nội dung minh họa có sẵn", count: 8 }],
            }
          : null,
    };
  });
}
function closeAttempt(s: any, a: any, auto = false) {
  if (a.submitted_at) return a.results;
  let score = 0,
    newCards = 0;
  const items = a.questions.map((q: any, n: number) => {
    const chosen = a.answers[q.id]?.chosen;
    if (!chosen)
      return {
        n: n + 1,
        question_id: q.id,
        topic: "Đo lường tần suất bệnh",
        status: "blank",
      };
    const f = grade(s, question(q.id), chosen, `attempt:${a.attempt_id}`);
    score += Number(f.correct);
    newCards += Number(f.card_created);
    return {
      n: n + 1,
      question_id: q.id,
      topic: "Đo lường tần suất bệnh",
      status: f.correct ? "ok" : "wrong",
    };
  });
  a.submitted_at = now();
  a.results = {
    ...summarizeAnswers(
      items.map((i: any) => ({
        question_id: i.question_id,
        correct: i.status === "ok",
      })),
      seed.questions,
      seed.blueprint.groups,
    ),
    attempt_id: a.attempt_id,
    title: a.title,
    score,
    total: items.length,
    wrong: items.filter((i: any) => i.status === "wrong").length,
    blank: items.filter((i: any) => i.status === "blank").length,
    submitted_at: a.submitted_at,
    duration_s: Math.max(
      0,
      Math.round((Date.now() - Date.parse(a.started_at)) / 1000),
    ),
    auto_submitted: auto,
    new_cards: newCards,
    priority_top: ["Đo lường tần suất bệnh"],
    priority_moved_up: [],
    items,
  };
  return a.results;
}
function getAttempt(s: any, id: number) {
  const a = s.attempts.find((a: any) => a.attempt_id === id);
  if (!a) fail(404, "attempt_not_found", "Không tìm thấy bài làm.");
  if (!a.submitted_at && Date.parse(a.deadline_at) <= Date.now())
    closeAttempt(s, a, true);
  return a;
}

export async function demoRequest(
  method: string,
  path: string,
  body: any = {},
) {
  const parsed = new URL(path, "http://demo.local");
  const p = parsed.pathname;
  const actor = getActor()!;
  if (!actor) fail(401, "unauthenticated", "Vui lòng đăng nhập.");
  const learnerPath =
    /^\/(home|me|consent|modules|units|session|practice-sets|cards|decks|chat|passages|messages|items|exams|attempts|progress|reports)/.test(
      p,
    );
  if (learnerPath && actor.role !== "learner")
    fail(403, "forbidden", "Vai trò này không có quyền học viên.");
  if (p.startsWith("/review") && !["reviewer", "admin"].includes(actor.role))
    fail(403, "forbidden", "Chỉ chuyên gia và quản trị viên được thẩm định.");
  if (
    p.startsWith("/admin") &&
    !["admin", "ministry_viewer"].includes(actor.role)
  )
    fail(403, "forbidden", "Bạn không có quyền quản lý.");
  return demoTransaction((s) => {
    if (
      learnerPath &&
      !/^\/(me|consent)/.test(p) &&
      !s.me.consent.service_given_at
    )
      fail(
        403,
        "consent_required",
        "Cần đồng ý sử dụng dịch vụ trước khi học.",
      );
    if (p === "/auth/logout") return { ok: true };
    if (p === "/consent/current") return examples.ConsentText;
    if (p === "/consent") {
      if (method === "DELETE") s.me.consent.research_given_at = null;
      else {
        s.me.consent = {
          version: body.version,
          service_given_at: body.service ? now() : null,
          research_given_at: body.research ? now() : null,
        };
      }
      return s.me.consent;
    }
    if (p === "/me/data")
      return {
        exported_at: now(),
        profile: s.me,
        responses: s.responses,
        attempts: s.attempts,
        cards: s.cards,
        chat_sessions: s.chats,
      };
    if (p === "/me") {
      if (method === "PATCH") Object.assign(s.me, body);
      if (method === "DELETE") {
        const clean = initial();
        Object.keys(s).forEach((key) => delete s[key]);
        Object.assign(s, clean);
        return { requested_at: now() };
      }
      return s.me;
    }
    if (p === "/modules")
      return {
        items: seed.blueprint.groups
          .map((g: any) => {
            const units =
              seed.modules.find((m: any) => m.module === `g${g.id}`)?.units ??
              [];
            return {
              id: `g${g.id}`,
              name: g.name,
              short_name: g.short_name,
              core_issue_group: g.id,
              coming_soon: !units.length,
              units_total: units.length,
              units_done: units.filter(
                (u: any) =>
                  s.units[u.id]?.cursor >= s.units[u.id]?.queue.length,
              ).length,
              topics_total: g.issues.length,
            };
          })
          .filter((m: any) => {
            const q = parsed.searchParams;
            const fold = (t: string) =>
              t
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "")
                .toLowerCase()
                .replace(/đ/g, "d");
            const units =
              seed.modules.find((a: any) => a.module === m.id)?.units ?? [];
            const codes = units.map((u: any) => u.competency_code);
            const started = units.some((u: any) => s.units[u.id]?.cursor > 0);
            const status =
              m.units_total > 0 && m.units_done === m.units_total
                ? "done"
                : started
                  ? "in_progress"
                  : "not_started";
            const levels = seed.questions
              .filter((x: any) => codes.includes(x.competency_code))
              .map((x: any) => x.bloom_level);
            return (
              (!q.get("q") ||
                fold(m.name + " " + m.short_name).includes(
                  fold(q.get("q")!),
                )) &&
              (!q.get("status") || status === q.get("status")) &&
              (!q.get("group") ||
                m.core_issue_group === Number(q.get("group"))) &&
              (!q.get("core_issue") ||
                codes.includes(
                  `CI-${q.get("core_issue")!.padStart(2, "0")}`,
                )) &&
              (!q.get("level") || levels.includes(Number(q.get("level"))))
            );
          }),
      };
    if (p.startsWith("/modules/")) {
      const id = p.split("/")[2],
        g = seed.blueprint.groups.find((g: any) => `g${g.id}` === id);
      return {
        id,
        name: g.name,
        short_name: g.short_name,
        units: (
          seed.modules.find((m: any) => m.module === id)?.units ?? []
        ).map((u: any) => ({
          id: u.id,
          topic: u.topic,
          done: unitView(s, u.id).done,
        })),
      };
    }
    if (p === "/home") {
      const ss = sessionToday(s);
      return {
        name: s.me.display_name,
        quick_review_count: ss.steps[0].count,
        quick_review_note_vi: "Theo lịch ôn của bạn",
        due_cards: ss.steps[0].count,
        next_mock: {
          form_id: "mock-demo",
          title: "Đề thi thử minh họa",
          n_questions: 10,
          minutes: 13,
          open_attempt_id:
            s.attempts.find((a: any) => !a.submitted_at)?.attempt_id ?? null,
        },
        tutor_suggestions: [
          {
            kind: "continue",
            text_vi: "Tiếp tục chủ đề đang học: đo lường tần suất bệnh.",
            action: { label_vi: "Học tiếp", target: "unit", id: "u-dt-01" },
          },
          {
            kind: "cards",
            text_vi: `${ss.steps[0].count} thẻ đang đến hạn.`,
            action: { label_vi: "Ôn thẻ", target: "cards", id: null },
          },
        ],
        recent: seed.modules[0].units.slice(0, 3).map((u: any) => {
          const v = unitView(s, u.id);
          return {
            kind: "unit",
            id: u.id,
            title: u.topic,
            subtitle_vi: "Học liệu minh họa chưa thẩm định",
            progress: v.total ? v.position / v.total : 0,
          };
        }),
      };
    }
    if (p === "/practice-sets" && method === "POST") {
      const count = Number(body.count);
      if (![5, 10, 20, 30, 60].includes(count))
        fail(422, "invalid_count", "Chọn 10, 20, 30 hoặc 60 câu.");
      const pool = seed.questions.filter(
        (q: any) =>
          !body.module_id ||
          `g${groupForQuestion(q, seed.blueprint.groups)?.id}` ===
            body.module_id,
      );
      if (!pool.length)
        fail(422, "no_questions", "Nhóm này đang xây dựng ngân hàng câu hỏi.");
      for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
      }
      const id = ++s.nextId;
      s.practice[id] = {
        id,
        source: "learner",
        competency_code: "",
        topic: body.module_id ? "Ôn theo nhóm năng lực" : "Ôn tập tổng hợp",
        completed: false,
        items: pool.slice(0, count).map((q: any, n: number) => ({
          question_id: q.id,
          n: n + 1,
          stem: q.stem,
          options: q.options.map(({ key, text }: any) => ({ key, text })),
          reason_vi: "Câu từ kho minh họa, chưa thẩm định.",
          chosen: null,
          feedback: null,
        })),
      };
      return practice(s, id);
    }
    if (p === "/session/today") return sessionToday(s);
    if (p === "/session/today/practice") return practice(s, 31);
    const pr = p.match(
      /^\/(?:practice-sets\/(\d+)|session\/today\/practice)(?:\/(responses|complete))?$/,
    );
    if (pr) {
      const id = Number(pr[1] ?? 31),
        set = practice(s, id);
      if (pr[2] === "responses") {
        const i = s.practice[id].items.find(
          (i: any) => i.question_id === body.question_id,
        );
        if (!i) fail(404, "question_not_found", "Câu không thuộc bộ luyện.");
        i.feedback = grade(
          s,
          question(i.question_id),
          body.chosen,
          `practice:${id}`,
        );
        i.chosen = body.chosen;
        return i.feedback;
      }
      if (pr[2] === "complete") {
        if (set.answered < set.total)
          fail(409, "incomplete", "Hãy trả lời đủ câu trước khi hoàn thành.");
        s.practice[id].completed = true;
        const correct = set.items.filter(
            (i: any) => i.feedback?.correct,
          ).length,
          newCards = set.items.filter(
            (i: any) => i.feedback?.card_created,
          ).length;
        return {
          graded: { correct, total: set.total },
          mastery_updated: null,
          cards_created: newCards ? { n: newCards } : null,
          tomorrow: null,
        };
      }
      return set;
    }
    const ur = p.match(/^\/units\/([^/]+)\/(next|responses|advance)$/);
    if (ur) {
      const id = ur[1],
        { u, state } = unitState(s, id);
      if (ur[2] === "responses") {
        const current = state.queue[state.cursor];
        if (current.id !== body.unit_item_id)
          fail(409, "not_current_item", "Câu này không còn là câu hiện tại.");
        const q = question(current.question),
          f = grade(s, q, body.chosen, `unit:${id}:${current.id}`);
        if (!f.correct && !current.remediation_added) {
          const extra = u.items.find((i: any) => i.after === current.id);
          if (extra) {
            state.queue.splice(state.cursor + 1, 0, clone(extra));
            current.remediation_added = true;
            f.remediation_inserted = true;
            f.remediation_note = "Đã thêm ví dụ từ học liệu minh họa.";
          }
        }
        state.cards_created = s.responses.filter(
          (r: any) =>
            r.context.startsWith(`unit:${id}:`) && r.feedback.card_created,
        ).length;
        return f;
      }
      if (ur[2] === "advance") {
        if (state.queue[state.cursor]?.id !== body.unit_item_id)
          fail(409, "not_current_item", "Bước học đã thay đổi.");
        state.cursor++;
      }
      return unitView(s, id);
    }
    if (p === "/cards/due") {
      const all = s.cards.filter(
        (c: any) => !c.suspended && Date.parse(c.due_at) <= Date.now(),
      );
      return { items: all, total_due: all.length };
    }
    if (p === "/decks")
      return {
        items: seed.blueprint.groups.slice(0, 1).map((g: any) => ({
          module_id: "g1",
          name: g.name,
          short_name: g.short_name,
          new: s.cards.filter((c: any) => !c.reviews).length,
          learning: s.cards.filter((c: any) => c.reviews).length,
          due: s.cards.filter(
            (c: any) => !c.suspended && Date.parse(c.due_at) <= Date.now(),
          ).length,
        })),
      };
    const cr = p.match(/^\/cards\/(\d+)(?:\/(reviews))?$/);
    if (cr) {
      const c = s.cards.find((c: any) => c.id === Number(cr[1]));
      if (!c) fail(404, "card_not_found", "Không tìm thấy thẻ.");
      if (cr[2]) {
        c.reviews++;
        c.due_at = new Date(
          Date.now() + c.preview[body.rating] * 1000,
        ).toISOString();
        return {
          card_id: c.id,
          due_at: c.due_at,
          remaining_due: s.cards.filter(
            (c: any) => !c.suspended && Date.parse(c.due_at) <= Date.now(),
          ).length,
        };
      }
      Object.assign(c, body);
      return { ok: true };
    }
    if (p === "/exams") {
      s.attempts
        .filter(
          (a: any) =>
            !a.submitted_at && Date.parse(a.deadline_at) <= Date.now(),
        )
        .forEach((a: any) => closeAttempt(s, a, true));
      return { items: forms(s) };
    }
    const start = p.match(/^\/exams\/([^/]+)\/attempts$/);
    if (start) {
      const f = forms(s).find((f: any) => f.id === start[1])!;
      if (!f) fail(404, "form_not_found", "Không tìm thấy đề.");
      const running = s.attempts.find(
        (a: any) => a.form_id === f.id && !a.submitted_at,
      );
      if (running && !body.fresh)
        return {
          ...running,
          remaining_s: Math.ceil(
            (Date.parse(running.deadline_at) - Date.now()) / 1000,
          ),
          submitted: false,
        };
      if (running) closeAttempt(s, running);
      const questions = seed.questions
        .slice(0, f.n_questions)
        .map((q: any, n: number) => ({
          id: q.id,
          n: n + 1,
          stem: q.stem,
          options: q.options.map(({ key, text }: any) => ({ key, text })),
        }));
      const a = {
        attempt_id: ++s.nextId,
        form_id: f.id,
        title: f.title,
        questions,
        answers: {},
        started_at: now(),
        deadline_at: new Date(
          Date.now() + questions.length * 75000,
        ).toISOString(),
        submitted_at: null,
        warning_s: 300,
      };
      s.attempts.unshift(a);
      return { ...a, remaining_s: questions.length * 75, submitted: false };
    }
    const ar = p.match(
      /^\/attempts\/(\d+)(?:\/(answers|submit|results|items)(?:\/([^/]+))?)?$/,
    );
    if (ar) {
      const a = getAttempt(s, Number(ar[1]));
      if (ar[2] === "answers") {
        if (a.submitted_at) fail(409, "attempt_closed", "Bài thi đã được nộp.");
        const q = a.questions.find((q: any) => q.id === ar[3]);
        if (!q)
          fail(404, "question_not_in_attempt", "Câu không thuộc bài thi.");
        if (body.chosen && !q.options.some((o: any) => o.key === body.chosen))
          fail(422, "unknown_option", "Phương án không hợp lệ.");
        a.answers[ar[3]!] = { chosen: body.chosen, flagged: body.flagged };
        return { ok: true };
      }
      if (ar[2] === "submit") return closeAttempt(s, a);
      if (ar[2] === "results") {
        if (!a.submitted_at)
          fail(409, "attempt_open", "Cần nộp bài trước khi xem kết quả.");
        return {
          ...a.results,
          ...summarizeAnswers(
            a.results.items.map((i: any) => ({
              question_id: i.question_id,
              correct: i.status === "ok",
            })),
            seed.questions,
            seed.blueprint.groups,
          ),
        };
      }
      if (ar[2] === "items") {
        if (!a.submitted_at)
          fail(409, "attempt_open", "Không được xem đáp án khi đang thi.");
        const q = question(ar[3]!);
        return {
          n: a.questions.findIndex((x: any) => x.id === q.id) + 1,
          total: a.questions.length,
          question_id: q.id,
          stem: q.stem,
          options: q.options.map((o: any) => ({ ...o, is_correct: o.correct })),
          chosen: a.answers[q.id]?.chosen ?? null,
          explanation: q.explanation,
          rationales: Object.fromEntries(
            q.options.map((o: any) => [o.key, o.rationale]),
          ),
          citations: citations(q.sources),
        };
      }
      return {
        ...a,
        remaining_s: Math.max(
          0,
          Math.ceil((Date.parse(a.deadline_at) - Date.now()) / 1000),
        ),
        submitted: !!a.submitted_at,
      };
    }
    if (p === "/progress/skills") {
      const v = clone(examples.ProgressSkills);
      v.coverage.assessed_topics = 0;
      v.coverage.modules.forEach((m: any) => (m.topics_assessed = 0));
      v.scope = parsed.searchParams.get("scope") ?? "latest3";
      v.days_to_exam = Math.max(
        0,
        Math.ceil((Date.parse(s.me.exam_date) - Date.now()) / 86400000),
      );
      const submitted = s.attempts
        .filter((a: any) => a.submitted_at)
        .sort(
          (a: any, b: any) =>
            Date.parse(b.submitted_at) - Date.parse(a.submitted_at) ||
            b.attempt_id - a.attempt_id,
        );
      const scoped = v.scope === "latest3" ? submitted.slice(0, 3) : submitted;
      v.mock_scores = scoped.map((a: any) => ({
        attempt_id: a.attempt_id,
        title: a.title,
        submitted_at: a.submitted_at,
        score: a.results.score,
        total: a.questions.length,
      }));
      const assessed = scoped.flatMap((a: any) =>
        a.results.items.map((i: any) => ({
          question_id: i.question_id,
          correct: i.status === "ok",
        })),
      );
      Object.assign(
        v,
        summarizeAnswers(assessed, seed.questions, seed.blueprint.groups),
      );
      v.priorities = v.specialties
        .filter((m: any) => m.total > m.correct)
        .sort((a: any, b: any) => a.correct / a.total - b.correct / b.total)
        .map((m: any, i: number) => ({
          rank: i + 1,
          competency_code: m.module_id,
          name: m.name,
          module_id: m.module_id,
          correct: m.correct,
          total: m.total,
          weakest_vi: null,
        }));
      return v;
    }
    if (p === "/progress/rhythm") {
      const v = clone(examples.ProgressRhythm);
      v.days_to_exam = Math.max(
        0,
        Math.ceil((Date.parse(s.me.exam_date) - Date.now()) / 86400000),
      );
      const forecast: Record<string, number> = {};
      for (const c of s.cards.filter((c: any) => !c.suspended)) {
        const date = new Intl.DateTimeFormat("en-CA", {
          timeZone: "Asia/Ho_Chi_Minh",
        }).format(new Date(Math.max(Date.now(), Date.parse(c.due_at))));
        forecast[date] = (forecast[date] ?? 0) + 1;
      }
      v.due_forecast = Object.entries(forecast)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, count]) => ({ date, count }));
      return v;
    }
    if (p.startsWith("/passages/")) {
      const v = passages.find((x: any) => x.id === p.split("/")[2]);
      if (!v) fail(404, "passage_not_found", "Không tìm thấy đoạn nguồn.");
      return v;
    }
    if (p === "/chat/sessions") {
      if (method === "POST") {
        if (
          s.attempts.some(
            (a: any) =>
              !a.submitted_at && Date.parse(a.deadline_at) > Date.now(),
          )
        )
          fail(
            409,
            "tutor_unavailable",
            "Không mở tutor khi đang có bài thi chưa nộp.",
          );
        if (
          body.question_id &&
          !s.responses.some((r: any) => r.question_id === body.question_id)
        )
          fail(409, "not_answered", "Hãy trả lời câu trước khi hỏi tutor.");
        if (
          body.question_id &&
          s.attempts.some(
            (a: any) =>
              !a.submitted_at &&
              a.questions.some((q: any) => q.id === body.question_id),
          )
        )
          fail(409, "tutor_unavailable", "Tutor không được mở trong bài thi.");
        const c = {
          id: ++s.nextId,
          title: body.title ?? "Cuộc trò chuyện mới",
          question_id: body.question_id ?? null,
          updated_at: now(),
          messages: [],
        };
        s.chats.unshift(c);
        return { id: c.id };
      }
      return {
        items: s.chats.map(({ messages: _messages, ...rest }: any) => rest),
        next_cursor: null,
      };
    }
    const cm = p.match(/^\/chat\/sessions\/(\d+)\/messages$/);
    if (cm) {
      const c = s.chats.find((c: any) => c.id === Number(cm[1]));
      if (!c) fail(404, "session_not_found", "Không tìm thấy cuộc trò chuyện.");
      return { items: c.messages, next_cursor: null };
    }
    if (p.startsWith("/messages/")) {
      const id = Number(p.split("/")[2]);
      for (const c of s.chats) {
        const m = c.messages.find((m: any) => m.id === id);
        if (m) m.helpful = body.helpful;
      }
      return { ok: true };
    }
    if (p.startsWith("/chat/suggestions/")) {
      const v = s.suggestions.find(
        (v: any) => v.id === Number(p.split("/")[3]),
      );
      if (!v) fail(404, "suggestion_not_found", "Không tìm thấy gợi ý.");
      if (v.kind === "add_to_tomorrow") {
        if (s.tomorrow && s.tomorrow !== v.id)
          fail(409, "tomorrow_taken", "Ngày mai đã có một chủ đề được thêm.");
        s.tomorrow = v.id;
        return {
          kind: v.kind,
          practice_set_id: null,
          for_date: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
        };
      }
      practice(s, 32);
      return { kind: "practise", practice_set_id: 32, for_date: null };
    }
    if (p.startsWith("/items/") && p.endsWith("/hint")) {
      if (
        s.attempts.some(
          (a: any) =>
            !a.submitted_at &&
            a.questions.some((q: any) => q.id === p.split("/")[2]),
        )
      )
        fail(409, "tutor_unavailable", "Không có gợi ý trong bài thi.");
      const q = question(p.split("/")[2]);
      return {
        text: "Hãy đối chiếu định nghĩa và xác định đúng tử số, mẫu số trong đoạn học liệu.",
        citations: citations(q.sources),
        generated: false,
      };
    }
    if (p === "/reports") {
      const id = ++s.nextId;
      s.reports.unshift({ id, ...body, status: "open", created_at: now() });
      return { id };
    }
    if (p === "/review/reports") return { items: s.reports, next_cursor: null };
    if (p === "/review/queue")
      return {
        items: s.review
          .filter((r: any) =>
            ["in_review_r1", "in_review_r2"].includes(r.status),
          )
          .map((r: any) => ({
            id: r.id,
            type: r.type,
            version: r.version,
            round: r.status === "in_review_r2" ? 2 : 1,
            status: r.status,
            group_id: 1,
            title: r.stem,
            flagged: false,
            ai_assisted: r.ai_assisted,
            waiting_since: now(),
          })),
        next_cursor: null,
      };
    const rv = p.match(/^\/review\/items\/([^/]+)(?:\/(decisions))?$/);
    if (rv) {
      const r = s.review.find((r: any) => r.id === rv[1]);
      if (!r) fail(404, "item_not_found", "Không tìm thấy mục.");
      if (rv[2]) {
        const round = r.status === "in_review_r2" ? 2 : 1;
        if (body.version !== r.version || body.round !== round)
          fail(
            409,
            "review_changed",
            "Phiên bản hoặc vòng thẩm định đã thay đổi.",
          );
        if (!["in_review_r1", "in_review_r2"].includes(r.status))
          fail(409, "review_closed", "Mục này không còn trong hàng đợi.");
        if (body.decision !== "pass" && !body.comment?.trim())
          fail(
            422,
            "comment_required",
            "Cần nhận xét khi chọn Cần sửa hoặc Loại.",
          );
        if (
          round === 2 &&
          r.decisions.some((d: any) => d.round === 1 && d.reviewer === actor.id)
        )
          fail(
            409,
            "different_reviewer_required",
            "Vòng 2 phải do chuyên gia khác thực hiện.",
          );
        const next =
          body.decision === "revise"
            ? "needs_revision"
            : body.decision === "reject"
              ? "rejected"
              : round === 1
                ? "in_review_r2"
                : "approved";
        r.decisions.push({ ...body, reviewer: actor.id, created_at: now() });
        r.transitions.push({
          from_status: r.status,
          to_status: next,
          actor: actor.id,
          at: now(),
          reason: body.comment,
        });
        r.status = next;
        return { id: r.id, version: r.version, status: next };
      }
      return r;
    }
    if (p.startsWith("/admin/dashboard/overview")) {
      const v = clone(examples.AdminOverview);
      v.ai_safety.model_versions = [];
      v.ai_safety.corpus_versions = ["fixture-giao-dien"];
      v.selected.period = parsed.searchParams.get("period") ?? v.period;
      v.period = v.selected.period;
      v.selected.school = parsed.searchParams.get("school");
      v.selected.region = parsed.searchParams.get("region");
      v.selected.audience = parsed.searchParams.get("audience");
      if (v.selected.school === "CSDT-F") {
        v.suppressed = true;
        v.kpis = null;
      }
      if (
        v.selected.school ||
        v.selected.audience ||
        v.selected.region ||
        v.period !== examples.AdminOverview.period
      ) {
        v.kpis = null;
        v.weekly_active = null;
        v.accuracy_by_module = null;
        v.schools = null;
        v.ai_safety = null;
        v.compliance = null;
      }
      return v;
    }
    fail(
      501,
      "not_implemented",
      "Chức năng này chưa được hỗ trợ trong bản trải nghiệm.",
    );
  });
}

export async function demoStream(
  path: string,
  body: any,
  onEvent: (event: string, data: any) => void,
) {
  const actor = getActor();
  if (actor?.role !== "learner")
    fail(403, "forbidden", "Chỉ người học được hỏi tutor.");
  const s = readStore();
  if (
    s.attempts.some(
      (a: any) => !a.submitted_at && Date.parse(a.deadline_at) > Date.now(),
    )
  )
    fail(
      409,
      "tutor_unavailable",
      "Không mở tutor khi đang có bài thi chưa nộp.",
    );
  if (!s.me.consent.service_given_at)
    fail(403, "consent_required", "Cần đồng ý trước khi hỏi.");
  const explain = path.match(/^\/items\/([^/]+)\/explain$/);
  let c = s.chats.find((c: any) => c.id === Number(path.split("/")[3]));
  const q = explain
    ? question(explain[1])
    : c?.question_id
      ? question(c.question_id)
      : null;
  const text = body.text ?? "Giải thích câu hỏi";
  if (
    q &&
    s.attempts.some(
      (a: any) =>
        !a.submitted_at && a.questions.some((x: any) => x.id === q.id),
    )
  )
    fail(409, "tutor_unavailable", "Tutor không được mở trong bài thi.");
  if (c) {
    c.title = c.title === "Cuộc trò chuyện mới" ? text.slice(0, 70) : c.title;
    c.messages.push({
      id: ++s.nextId,
      role: "user",
      text,
      created_at: now(),
      citations: [],
      trace: [],
      suggestions: [],
      clarify_options: [],
      searched: [],
      state: null,
      notice: null,
      helpful: null,
      trace_summary: null,
      nearest_chapter: null,
      format: null,
    });
  }
  const clinical =
    /bệnh nhân của|bệnh nhân tôi|kê đơn|tôi đang đau|con tôi|điều trị cho tôi/i.test(
      text,
    );
  const ambiguous = !q && /^(tỷ lệ|ty le|tỉ lệ)\??$/i.test(text.trim());
  const normalized = text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  const terms = normalized.split(/\W+/).filter((w: string) => w.length > 3);
  let found = q
    ? q.sources.map((id: string) => passages.find((p: any) => p.id === id))
    : passages
        .map((p: any) => ({
          p,
          score: terms.filter((w: string) =>
            p.excerpt
              .normalize("NFD")
              .replace(/[\u0300-\u036f]/g, "")
              .toLowerCase()
              .includes(w),
          ).length,
        }))
        .filter(
          (x: any) => x.score >= Math.min(2, terms.length) && terms.length > 0,
        )
        .sort((a: any, b: any) => b.score - a.score)
        .slice(0, 2)
        .map((x: any) => x.p);
  if (clinical || ambiguous) found = [];
  const trace: any[] = [];
  const step = (kind: string, label: string) => {
    const event = { id: kind, kind, label_vi: label, status: "running" };
    onEvent("step", event);
    trace.push({ ...event, status: "done" });
    onEvent("step", { ...event, status: "done" });
  };
  if (!clinical && !ambiguous) {
    step("search", "Tìm trong học liệu minh họa");
    if (found.length) step("read", `Đọc ${found.length} đoạn nguồn có sẵn`);
  }
  onEvent("status", { status: "checking_sources" });
  if (found.length) step("check", "Luồng kiểm tra minh họa — chưa hậu kiểm AI");
  const state = clinical
    ? "declined"
    : ambiguous
      ? "needs_clarification"
      : found.length
        ? "answered"
        : "insufficient_evidence";
  const answer = clinical
    ? "Nền tảng chỉ hỗ trợ ôn tập. Yêu cầu tư vấn cho người bệnh cụ thể nằm ngoài phạm vi."
    : ambiguous
      ? "Bạn muốn hỏi về tỷ lệ hiện mắc hay tỷ lệ mới mắc?"
      : found.length
        ? q
          ? q.explanation + " [1]"
          : found
              .map(
                (p: any, i: number) =>
                  p.excerpt
                    .split(/(?<=[.!?])\s/)
                    .slice(0, 3)
                    .join(" ") + ` [${i + 1}]`,
              )
              .join("\n\n")
        : "Không đủ bằng chứng trong kho minh họa để trả lời câu này. Hãy chọn chủ đề có học liệu hoặc diễn đạt lại.";
  const cites = citations(found.map((p: any) => p.id));
  const messageId = ++s.nextId;
  const suggestions =
    state === "answered" && !explain
      ? [
          {
            id: ++s.nextId,
            kind: "practise",
            label_vi: "Luyện câu cùng chủ đề",
            reason_vi: "Chỉ dùng câu từ ngân hàng minh họa.",
            n_items: 6,
          },
          {
            id: ++s.nextId,
            kind: "add_to_tomorrow",
            label_vi: "Thêm vào ngày mai",
            reason_vi: "Chỉ áp dụng khi bạn chấp nhận.",
            n_items: null,
          },
        ]
      : [];
  s.suggestions.push(...suggestions);
  const final = {
    state,
    message_id: messageId,
    trace_summary: null,
    clarify_options: ambiguous
      ? [
          {
            term: "hiện mắc",
            label_vi: "Tỷ lệ hiện mắc",
            query: "Tỷ lệ hiện mắc là gì?",
          },
          {
            term: "mới mắc",
            label_vi: "Tỷ lệ mới mắc",
            query: "Tỷ lệ mới mắc là gì?",
          },
        ]
      : [],
    searched: found.map((p: any) => ({
      document: p.document,
      range: `Trang ${p.page}`,
    })),
    nearest_chapter: null,
    suggestions,
  };
  const notice =
    "Phản hồi được dựng từ đoạn nguồn có sẵn để kiểm tra FE; không có mô hình AI được gọi, không phải kết quả hậu kiểm y khoa.";
  onEvent("answer", { text: answer, citations: cites, notice });
  onEvent("final", final);
  if (c) {
    c.messages.push({
      id: messageId,
      role: "assistant",
      text: answer,
      created_at: now(),
      format: "text",
      citations: cites,
      notice,
      trace,
      ...final,
      helpful: null,
    });
    c.updated_at = now();
  }
  writeStore(s);
}
