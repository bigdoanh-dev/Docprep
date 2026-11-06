import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { setActor, type Role } from "../src/app/identity.ts";
import {
  demoCall,
  demoRequest,
  demoStream,
  readStore,
  resetDemo,
  seed,
  writeStore,
} from "../src/lib/demo/store.ts";
const memory = new Map<string, string>();
Object.defineProperty(globalThis, "localStorage", {
  value: {
    getItem: (k: string) => memory.get(k) ?? null,
    setItem: (k: string, v: string) => memory.set(k, v),
    removeItem: (k: string) => memory.delete(k),
  },
  configurable: true,
});
Object.defineProperty(globalThis, "window", {
  value: new EventTarget(),
  configurable: true,
});
function actor(role: Role = "learner", id = "demo-learner") {
  setActor({ role, id, name: "Test", mode: "demo" });
}
async function ready() {
  actor();
  await demoRequest("POST", "/consent", {
    version: "2026-10",
    service: true,
    research: false,
  });
}
beforeEach(() => {
  memory.clear();
  actor();
  resetDemo();
});
test("consent is required; research consent is optional", async () => {
  await assert.rejects(demoRequest("GET", "/home"), {
    code: "consent_required",
  });
  await ready();
  assert.equal(
    (await demoRequest("GET", "/me")).consent.research_given_at,
    null,
  );
  assert.ok((await demoRequest("GET", "/home")).recent.length);
});
test("API role separation refuses reviewer learner data and learner review queue", async () => {
  await ready();
  await assert.rejects(demoRequest("GET", "/review/queue"), {
    code: "forbidden",
  });
  actor("reviewer", "demo-reviewer-1");
  await assert.rejects(demoRequest("GET", "/me"), { code: "forbidden" });
  assert.equal((await demoRequest("GET", "/review/queue")).items.length, 4);
});
test("card review retries apply one change per intent", async () => {
  await ready();
  const [a, b] = await Promise.all([
    demoCall("POST", "/cards/1/reviews", { rating: 3 }, "same-key"),
    demoCall("POST", "/cards/1/reviews", { rating: 3 }, "same-key"),
  ]);
  assert.deepEqual(a, b);
  assert.equal(readStore().cards[0].reviews, 1);
  await demoCall("POST", "/cards/1/reviews", { rating: 3 }, "same-key");
  assert.equal(readStore().cards[0].reviews, 1);
});
test("exam hides keys, resumes saved answers, blocks tutor, and submits once", async () => {
  await ready();
  const a = await demoRequest("POST", "/exams/mock-demo/attempts");
  const q = a.questions[0];
  assert.equal(q.options[0].correct, undefined);
  await demoRequest("PUT", `/attempts/${a.attempt_id}/answers/${q.id}`, {
    chosen: q.options[0].key,
    flagged: true,
  });
  const resumed = await demoRequest("GET", `/attempts/${a.attempt_id}`);
  assert.equal(resumed.answers[q.id].flagged, true);
  await assert.rejects(
    demoRequest("GET", `/attempts/${a.attempt_id}/results`),
    { code: "attempt_open" },
  );
  await assert.rejects(demoRequest("POST", "/chat/sessions"), {
    code: "tutor_unavailable",
  });
  await assert.rejects(
    demoStream(
      "/chat/sessions/99/messages",
      { text: "Hiện mắc là gì?" },
      () => {},
    ),
    { code: "tutor_unavailable" },
  );
  const result = await demoRequest("POST", `/attempts/${a.attempt_id}/submit`);
  assert.equal(result.blank, 9);
  assert.deepEqual(
    await demoRequest("POST", `/attempts/${a.attempt_id}/submit`),
    result,
  );
  await assert.rejects(
    demoRequest("PUT", `/attempts/${a.attempt_id}/answers/${q.id}`, {
      chosen: null,
    }),
    { code: "attempt_closed" },
  );
});
test("an expired attempt becomes submitted without resetting its deadline", async () => {
  await ready();
  const a = await demoRequest("POST", "/exams/diagnostic-demo/attempts");
  const s = readStore();
  s.attempts[0].deadline_at = new Date(Date.now() - 1).toISOString();
  writeStore(s);
  const v = await demoRequest("GET", `/attempts/${a.attempt_id}`);
  assert.equal(v.submitted, true);
  assert.equal(
    (await demoRequest("GET", `/attempts/${a.attempt_id}/results`))
      .auto_submitted,
    true,
  );
});
test("practice requires all answers and creates no duplicate cards on retry", async () => {
  await ready();
  const p = await demoRequest("GET", "/practice-sets/31");
  await assert.rejects(demoRequest("POST", "/practice-sets/31/complete"), {
    code: "incomplete",
  });
  for (const item of p.items) {
    const q = seed.questions.find((q: any) => q.id === item.question_id);
    const chosen = q.options.find((o: any) => !o.correct).key;
    await demoRequest("POST", "/practice-sets/31/responses", {
      question_id: q.id,
      chosen,
    });
    await demoRequest("POST", "/practice-sets/31/responses", {
      question_id: q.id,
      chosen,
    });
  }
  assert.equal(readStore().responses.length, p.total);
  assert.equal(
    new Set(readStore().cards.map((c: any) => c.source_question_id)).size,
    readStore().cards.length,
  );
  const done = await demoRequest("POST", "/practice-sets/31/complete");
  assert.equal(done.graded.correct, 0);
  assert.equal(done.mastery_updated, null);
});
test("two review rounds require independent reviewers and mandatory revision comments", async () => {
  actor("reviewer", "demo-reviewer-1");
  const r = (await demoRequest("GET", "/review/queue")).items[0];
  await assert.rejects(
    demoRequest("POST", `/review/items/${r.id}/decisions`, {
      version: 1,
      round: 1,
      decision: "revise",
      comment: "",
    }),
    { code: "comment_required" },
  );
  await demoRequest("POST", `/review/items/${r.id}/decisions`, {
    version: 1,
    round: 1,
    decision: "pass",
  });
  await assert.rejects(
    demoRequest("POST", `/review/items/${r.id}/decisions`, {
      version: 1,
      round: 2,
      decision: "pass",
    }),
    { code: "different_reviewer_required" },
  );
  actor("reviewer", "demo-reviewer-2");
  const final = await demoRequest("POST", `/review/items/${r.id}/decisions`, {
    version: 1,
    round: 2,
    decision: "pass",
  });
  assert.equal(final.status, "approved");
  assert.equal(
    (await demoRequest("GET", `/review/items/${r.id}`)).decisions.length,
    2,
  );
});
test("demo answer events preserve source links and do not apply plan suggestions automatically", async () => {
  await ready();
  const c = await demoRequest("POST", "/chat/sessions");
  const events: any[] = [];
  await demoStream(
    `/chat/sessions/${c.id}/messages`,
    { text: "Phân biệt tỷ lệ hiện mắc" },
    (e, d) => events.push([e, d]),
  );
  assert.equal(events.at(-1)[0], "final");
  const answer = events.find((e) => e[0] === "answer")[1];
  assert.ok(answer.citations.length);
  assert.match(answer.text, /\[1\]/);
  assert.match(answer.notice, /không có mô hình AI/);
  assert.equal(events.at(-1)[1].trace_summary, null);
  assert.equal(readStore().tomorrow, null);
  const suggestion = events
    .at(-1)[1]
    .suggestions.find((s: any) => s.kind === "add_to_tomorrow");
  await demoRequest("POST", `/chat/suggestions/${suggestion.id}/accept`);
  assert.equal(readStore().tomorrow, suggestion.id);
});
test("demo clarifies ambiguous questions and refuses patient-specific requests", async () => {
  await ready();
  const c = await demoRequest("POST", "/chat/sessions");
  for (const [text, state] of [
    ["tỷ lệ", "needs_clarification"],
    ["kê đơn cho tôi", "declined"],
    ["zzyyww", "insufficient_evidence"],
  ]) {
    let final: any;
    await demoStream(`/chat/sessions/${c.id}/messages`, { text }, (e, d) => {
      if (e === "final") final = d;
    });
    assert.equal(final.state, state);
    assert.equal(final.suggestions.length, 0);
  }
});
test("demo does not reuse nationwide statistics under a selected school filter", async () => {
  actor("ministry_viewer", "demo-ministry");
  const national = await demoRequest("GET", "/admin/dashboard/overview");
  assert.ok(national.kpis);
  const subset = await demoRequest(
    "GET",
    "/admin/dashboard/overview?school=CSDT-A",
  );
  assert.equal(subset.kpis, null);
  const small = await demoRequest(
    "GET",
    "/admin/dashboard/overview?school=CSDT-F",
  );
  assert.equal(small.suppressed, true);
});
test("deleting demo account clears entered profile and learning state and requires consent again", async () => {
  await ready();
  await demoRequest("PATCH", "/me", { display_name: "Tên nhập khi kiểm tra" });
  await demoRequest("POST", "/chat/sessions");
  await demoRequest("DELETE", "/me");
  const next = readStore();
  assert.equal(next.chats.length, 0);
  assert.equal(next.responses.length, 0);
  assert.equal(next.me.display_name, "Nguyễn Thu Hà");
  assert.equal(next.me.consent.service_given_at, null);
  await assert.rejects(demoRequest("GET", "/home"), {
    code: "consent_required",
  });
});
test("unit retries do not inflate the count of newly created cards", async () => {
  await ready();
  let view = await demoRequest("GET", "/units/u-dt-01/next");
  while (!view.done) {
    const item = view.item;
    if (item.question) {
      const q = seed.questions.find((q: any) => q.id === item.question.id);
      const body = {
        unit_item_id: item.unit_item_id,
        chosen: q.options.find((o: any) => !o.correct).key,
      };
      const first = await demoRequest("POST", "/units/u-dt-01/responses", body);
      if (first.card_created) {
        const count = (await demoRequest("GET", "/units/u-dt-01/next"))
          .cards_created;
        await demoRequest("POST", "/units/u-dt-01/responses", body);
        assert.equal(
          (await demoRequest("GET", "/units/u-dt-01/next")).cards_created,
          count,
        );
        return;
      }
    }
    view = await demoRequest("POST", "/units/u-dt-01/advance", {
      unit_item_id: item.unit_item_id,
    });
  }
  assert.fail("The fixture must exercise a question that creates a new card");
});

test("custom practice validates count and group, keeps unique questions and conceals keys", async () => {
  await ready();
  const set: any = await demoCall(
    "POST",
    "/practice-sets",
    { count: 20, module_id: "g1" },
    "create-practice",
  );
  assert.equal(set.items.length, 20);
  assert.equal(new Set(set.items.map((q: any) => q.question_id)).size, 20);
  assert.equal(set.items[0].options[0].correct, undefined);
  assert.deepEqual(
    await demoCall(
      "POST",
      "/practice-sets",
      { count: 20, module_id: "g1" },
      "create-practice",
    ),
    set,
  );
  await assert.rejects(demoCall("POST", "/practice-sets", { count: 500 }), {
    code: "invalid_count",
  });
  await assert.rejects(
    demoCall("POST", "/practice-sets", { count: 5, module_id: "g2" }),
    { code: "no_questions" },
  );
});

test("mock specialties and Bloom respect selected scope and submitted results only", async () => {
  await ready();
  assert.equal(
    (await demoRequest("GET", "/progress/skills?scope=all")).levels.every(
      (l: any) => l.total === 0,
    ),
    true,
  );
  for (let n = 0; n < 4; n++) {
    const a = await demoRequest("POST", "/exams/mock-demo/attempts");
    await demoRequest(
      "PUT",
      `/attempts/${a.attempt_id}/answers/${a.questions[0].id}`,
      { chosen: a.questions[0].options[0].key, flagged: false },
    );
    const results = await demoRequest(
      "POST",
      `/attempts/${a.attempt_id}/submit`,
    );
    assert.equal(
      results.specialties.reduce((n: number, s: any) => n + s.total, 0),
      10,
    );
  }
  const all = await demoRequest("GET", "/progress/skills?scope=all"),
    latest = await demoRequest("GET", "/progress/skills?scope=latest3");
  assert.equal(all.mock_scores.length, 4);
  assert.equal(latest.mock_scores.length, 3);
  assert.equal(
    all.levels.reduce((n: number, l: any) => n + l.total, 0),
    40,
  );
  assert.equal(
    latest.levels.reduce((n: number, l: any) => n + l.total, 0),
    30,
  );
});

test("module filters combine metadata without inventing core issue mappings for foundation questions", async () => {
  await ready();
  const matching = await demoRequest(
    "GET",
    "/modules?q=suc+khoe+quan+the&group=1&level=1",
  );
  assert.deepEqual(
    matching.items.map((m: any) => m.id),
    ["g1"],
  );
  assert.equal(
    (await demoRequest("GET", "/modules?group=2&level=1")).items.length,
    0,
  );
  assert.equal(
    (await demoRequest("GET", "/modules?core_issue=1")).items.length,
    0,
  );
  assert.equal(
    (await demoRequest("GET", "/modules?status=done")).items.length,
    0,
  );
});
