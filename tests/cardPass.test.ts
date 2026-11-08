import assert from "node:assert/strict";
import { test } from "node:test";
import { loadCardPass, passSummary } from "../src/lib/cardPass.ts";
import type { DueCard } from "../src/lib/api";

test("the pass says what was done", () => {
  assert.deepEqual(passSummary([3, 1, 4]), {
    title: "Xong 3 thẻ",
    recall: "Nhớ đúng 2/3",
    forgotten: "1 thẻ bạn quên sẽ quay lại trong hôm nay",
  });
  assert.deepEqual(passSummary([2, 3]), {
    title: "Xong 2 thẻ",
    recall: "Nhớ đúng 2/2",
    forgotten: null,
  });
  assert.deepEqual(passSummary([]), {
    title: "Không còn thẻ nào đến hạn",
    recall: null,
    forgotten: null,
  });
});

test("a 250-card session loads all cards in API-sized pages before ratings change the queue", async () => {
  const cards: DueCard[] = Array.from({ length: 250 }, (_, i) => ({
    id: i + 1,
    front: "Câu hỏi",
    back: "Đáp án",
    citation: "Nguồn",
    source_passage_id: "p1",
    origin: "Từ quiz học phần",
    module: "g1",
    preview: { "1": 60, "2": 300, "3": 600, "4": 900 },
  }));
  const calls: number[][] = [];
  const loaded = await loadCardPass(250, async (limit, offset) => {
    assert.ok(limit >= 1 && limit <= 200);
    calls.push([limit, offset]);
    return {
      items: cards.slice(offset, offset + limit),
      total_due: cards.length,
    };
  });
  assert.deepEqual(calls, [
    [200, 0],
    [50, 200],
  ]);
  assert.deepEqual(
    loaded.map((c) => c.id),
    cards.map((c) => c.id),
  );
  // Limits can shrink since a session was built: never loop or request an invalid empty page.
  assert.equal(
    (await loadCardPass(250, async () => ({ items: [], total_due: 0 }))).length,
    0,
  );
});
