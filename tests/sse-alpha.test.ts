import { test } from "node:test";
import assert from "node:assert/strict";
import { readEvents, STREAM_BROKEN } from "../src/lib/sseRead";
import { applyEvent, failTurn, startTurn } from "../src/lib/chatTurn";
import { minimiseText } from "../src/lib/privacy";

test("SSE parses split CRLF, heartbeat and event IDs", async () => {
  const wire = new TextEncoder().encode(': heartbeat\r\n\r\nid: 7-1\r\nevent: final\r\ndata: {"turn_status":"cancelled","error":{"message_vi":"Đã hủy"}}\r\n\r\n');
  let i = 0;
  const seen: unknown[] = [];
  await readEvents({ async read() { return i < wire.length ? { done: false, value: wire.slice(i, ++i) } : { done: true }; } },
    (event, data, id) => seen.push([event, data.turn_status, id]));
  assert.deepEqual(seen, [["final", "cancelled", "7-1"]]);
});

test("technical terminal is an error, not insufficient evidence", () => {
  const turn = applyEvent(startTurn(), "final", { turn_status: "failed", state: null, message_id: null,
    error: { message_vi: "Model tạm ngừng" } });
  assert.equal(turn.phase, "failed");
  assert.equal(turn.error, "Model tạm ngừng");
  assert.equal(turn.state, null);
});

test("client minimises identifiers before sending chat", () => {
  const safe = minimiseText("a@example.org 0912345678 at_secret HV-000001");
  assert.equal(safe, "[REDACTED] [REDACTED] [REDACTED] [REDACTED]");
});

test("SSE preserves Vietnamese when UTF-8 characters cross network chunks", async () => {
  const wire = new TextEncoder().encode(
    'event: answer\ndata: {"text":"Tỷ lệ hiện mắc [1]","citations":[]}\n\nevent: final\ndata: {"state":"answered","message_id":12}\n\n',
  );
  let offset = 0;
  let turn = startTurn();
  await readEvents(
    {
      async read() {
        if (offset >= wire.length) return { done: true };
        const value = wire.slice(offset, offset + 2);
        offset += 2;
        return { done: false, value };
      },
    },
    (event, data) => {
      turn = applyEvent(turn, event, data);
    },
  );
  assert.equal(turn.phase, "done");
  assert.equal(turn.text, "Tỷ lệ hiện mắc [1]");
  assert.equal(turn.messageId, 12);
});

test("network interruption produces the Vietnamese connection error", async () => {
  await assert.rejects(
    readEvents(
      {
        async read() {
          throw new Error("socket closed");
        },
      },
      () => {},
    ),
    { message: STREAM_BROKEN },
  );
});

test("an interrupted turn ends all spinning steps without claiming a final answer", () => {
  const working = applyEvent(startTurn(), "step", {
    id: "s1",
    kind: "search",
    label_vi: "Đang tìm",
    status: "running",
  });
  const failed = failTurn(working, STREAM_BROKEN);
  assert.equal(failed.phase, "failed");
  assert.equal(failed.state, null);
  assert.equal(failed.steps[0].status, "done");
});
