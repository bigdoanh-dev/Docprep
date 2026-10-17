import assert from "node:assert/strict";
import { test } from "node:test";
import { STREAM_BROKEN, readEvents } from "../src/lib/sseRead.ts";

const bytes = (s: string) => new TextEncoder().encode(s);

function reader(chunks: (string | Error)[]) {
  let i = 0;
  return {
    read: async (): Promise<{ value?: Uint8Array; done: boolean }> => {
      if (i >= chunks.length) return { done: true };
      const next = chunks[i++];
      if (next instanceof Error) throw next;
      return { value: bytes(next), done: false };
    },
  };
}

test("events are read across chunk boundaries", async () => {
  const seen: [string, unknown][] = [];
  await readEvents(
    reader([
      'event: step\ndata: {"id":"s1"}\n',
      '\nevent: final\ndata: {"state":"answered"}\n\n',
    ]),
    (event, data) => seen.push([event, data]),
  );
  assert.deepEqual(seen, [
    ["step", { id: "s1" }],
    ["final", { state: "answered" }],
  ]);
});

test("a connection that drops half-way says so in Vietnamese, after what did arrive", async () => {
  const seen: string[] = [];
  await assert.rejects(
    readEvents(
      reader([
        'event: step\ndata: {"id":"s1"}\n\n',
        new TypeError("network error"),
      ]),
      (event) => seen.push(event),
    ),
    (e: Error) => e.message === STREAM_BROKEN,
  );
  assert.deepEqual(seen, ["step"]);
  assert.equal(
    STREAM_BROKEN,
    "Mất kết nối với máy chủ giữa chừng. Vui lòng thử lại.",
  );
});
