import { test } from "node:test";
import assert from "node:assert/strict";
import { readEvents, STREAM_BROKEN } from "../src/lib/sseRead";
import { applyEvent, failTurn, startTurn } from "../src/lib/chatTurn";

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
