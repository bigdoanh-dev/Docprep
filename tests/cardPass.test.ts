import assert from "node:assert/strict";
import { test } from "node:test";
import { passSummary } from "../src/lib/cardPass.ts";

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
