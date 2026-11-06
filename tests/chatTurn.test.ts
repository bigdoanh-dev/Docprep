import assert from "node:assert/strict";
import { test } from "node:test";
import {
  applyEvent,
  chipLabel,
  failTurn,
  fromStored,
  startTurn,
  type StoredMessage,
  type TurnView,
} from "../src/lib/chatTurn.ts";

const step = (
  id: string,
  kind: string,
  label: string,
  status: "running" | "done",
) => ({ id, kind, label_vi: label, status });
const CITE = {
  n: 1,
  passage_id: "tc-p02",
  document: "Lịch tiêm chủng mở rộng",
  chapter: null,
  section: null,
  page: 8,
  article: null,
};
const SUMMARY = { sources: 1, claims_checked: 2, claims_removed: 1 };
const SUGGESTION = {
  id: 7,
  kind: "practise" as const,
  label_vi: "Luyện 3 câu đã duyệt",
  reason_vi: "Bạn đã trả lời sai 2 câu…",
  n_items: 3,
};

function play(events: [string, unknown][]): TurnView {
  return events.reduce(
    (view, [event, data]) => applyEvent(view, event, data),
    startTurn(),
  );
}

const LIVE: [string, unknown][] = [
  ["status", { status: "queued", position: 3 }],
  ["status", { status: "queued", position: 2 }],
  ["step", step("s1", "search", "Đang tìm trong 9 tài liệu", "running")],
  ["step", step("s1", "search", "Đã tìm trong 9 tài liệu", "done")],
  ["step", step("s2", "read", "Đang đọc 2 đoạn", "running")],
  ["step", step("s2", "read", "Đã đọc: Lịch tiêm chủng mở rộng tr. 8", "done")],
  ["status", { status: "answering", position: null }],
  ["status", { status: "checking_sources", position: null }],
  ["step", step("s3", "check", "Đang kiểm tra nhận định với nguồn", "running")],
  ["step", step("s3", "check", "Đã kiểm tra 2 nhận định", "done")],
  [
    "answer",
    {
      text: "Tiêm trong 24 giờ đầu. [1]",
      format: "text",
      citations: [CITE],
      notice: "Đã bỏ 1 ý vì không tìm được nguồn trong giáo trình.",
    },
  ],
  [
    "final",
    {
      state: "answered",
      message_id: 58,
      format: "text",
      trace_summary: SUMMARY,
      clarify_options: [],
      searched: [],
      nearest_chapter: null,
      suggestions: [SUGGESTION],
    },
  ],
];

test("a whole live turn folds into one view", () => {
  const queued = play(LIVE.slice(0, 2));
  assert.equal(queued.phase, "queued");
  assert.equal(queued.position, 2);
  const working = play(LIVE.slice(0, 5));
  assert.equal(working.phase, "working");
  assert.equal(working.position, null);
  assert.deepEqual(
    working.steps.map((s) => [s.id, s.status]),
    [
      ["s1", "done"],
      ["s2", "running"],
    ],
  );
  const view = play(LIVE);
  assert.equal(view.phase, "done");
  assert.deepEqual(
    view.steps.map((s) => s.label_vi),
    [
      "Đã tìm trong 9 tài liệu",
      "Đã đọc: Lịch tiêm chủng mở rộng tr. 8",
      "Đã kiểm tra 2 nhận định",
    ],
  );
  assert.equal(view.text, "Tiêm trong 24 giờ đầu. [1]");
  assert.equal(view.state, "answered");
  assert.equal(view.messageId, 58);
  assert.deepEqual(view.summary, SUMMARY);
  assert.deepEqual(view.suggestions, [SUGGESTION]);
  assert.equal(
    view.notice,
    "Đã bỏ 1 ý vì không tìm được nguồn trong giáo trình.",
  );
});

test("a step sent twice is one step, kept where it first appeared", () => {
  const view = play([
    ["step", step("s1", "search", "a", "running")],
    ["step", step("s2", "read", "b", "running")],
    ["step", step("s1", "search", "A", "done")],
  ]);
  assert.deepEqual(
    view.steps.map((s) => [s.id, s.label_vi, s.status]),
    [
      ["s1", "A", "done"],
      ["s2", "b", "running"],
    ],
  );
});

test("an unknown event changes nothing", () => {
  const before = play(LIVE.slice(0, 4));
  assert.deepEqual(applyEvent(before, "heartbeat", {}), before);
});

test("a stream that stops shows no running step", () => {
  const view = failTurn(play(LIVE.slice(0, 5)), "Không kết nối được máy chủ.");
  assert.equal(view.phase, "failed");
  assert.equal(view.error, "Không kết nối được máy chủ.");
  assert.ok(view.steps.every((s) => s.status === "done"));
  assert.equal(view.position, null);
});

test("a stored message gives the view the live turn gave", () => {
  const stored: StoredMessage = {
    id: 58,
    role: "assistant",
    text: "Tiêm trong 24 giờ đầu. [1]",
    created_at: "2026-10-12T08:00:00Z",
    state: "answered",
    format: "text",
    citations: [CITE],
    notice: "Đã bỏ 1 ý vì không tìm được nguồn trong giáo trình.",
    trace_summary: SUMMARY,
    clarify_options: [],
    searched: [],
    nearest_chapter: null,
    suggestions: [SUGGESTION],
    helpful: true,
    trace: [
      step("s1", "search", "Đã tìm trong 9 tài liệu", "done"),
      step("s2", "read", "Đã đọc: Lịch tiêm chủng mở rộng tr. 8", "done"),
      step("s3", "check", "Đã kiểm tra 2 nhận định", "done"),
    ],
  };
  const view = fromStored(stored);
  assert.deepEqual(
    { ...view, helpful: null },
    { ...play(LIVE), helpful: null },
  );
  assert.equal(view.helpful, true);
});

test("the chip says what was checked, or the last thing done", () => {
  assert.equal(chipLabel(play(LIVE)), "Đã tra 1 nguồn · kiểm tra 2 nhận định");
  const searchedOnly = play([
    ["step", step("s1", "search", "Đã tìm trong 9 tài liệu", "done")],
    [
      "final",
      {
        state: "insufficient_evidence",
        message_id: 1,
        trace_summary: null,
        clarify_options: [],
        searched: [],
        nearest_chapter: null,
        suggestions: [],
      },
    ],
  ]);
  assert.equal(chipLabel(searchedOnly), "Đã tìm trong 9 tài liệu");
  assert.equal(chipLabel(startTurn()), null);
});
