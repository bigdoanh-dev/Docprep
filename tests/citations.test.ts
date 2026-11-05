import test from "node:test";
import assert from "node:assert/strict";
import { groupCitations } from "../src/lib/citations";
import type { Citation } from "../src/lib/api";
const citation = {
  n: 1,
  passage_id: "a",
  document: "Tài liệu A",
  chapter: "Chương 1",
  section: null,
  page: 10,
  article: null,
} as Citation;
test("grouping removes duplicate references and preserves distinct passages and pages", () => {
  const groups = groupCitations([
    citation,
    citation,
    { ...citation, passage_id: "b", page: 11 },
    { ...citation, passage_id: "c", document: "Tài liệu B" },
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0][0], "Tài liệu A");
  assert.deepEqual(
    groups[0][1].map((c) => [c.passage_id, c.page]),
    [
      ["a", 10],
      ["b", 11],
    ],
  );
  assert.equal(groups[1][0], "Tài liệu B");
});
test("an empty source list remains empty", () => {
  assert.deepEqual(groupCitations([]), []);
});
