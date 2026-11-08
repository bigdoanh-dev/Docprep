import test from "node:test";
import assert from "node:assert/strict";
import blueprint from "../src/lib/blueprint.json";
import {
  assessmentPercent,
  summarizeAnswers,
} from "../src/lib/learningAnalytics";

test("the curriculum contains exactly 54 distinct issues in their eight groups", () => {
  assert.deepEqual(
    blueprint.groups.map((g) => g.issues.length),
    [5, 11, 3, 8, 2, 19, 3, 3],
  );
  assert.deepEqual(
    blueprint.groups.flatMap((g) => g.issues.map((i) => i.id)),
    Array.from({ length: 54 }, (_, i) => i + 1),
  );
  assert.equal(
    blueprint.groups[3].issues.find((i) => i.id === 24)?.name,
    "Hội chứng viêm long đường hô hấp trên",
  );
});

test("issue counts use exact question metadata and preserve unassessed issues", () => {
  const questions = [
    { id: "a", competency_code: "CI-1", bloom_level: 1 },
    { id: "b", competency_code: "CI-2", bloom_level: 2 },
    { id: "c", competency_code: "CI-6", bloom_level: 3 },
    { id: "foundation", competency_code: "FND", bloom_level: 1 },
    { id: "unknown", competency_code: "CI-999", bloom_level: 6 },
  ];
  const result = summarizeAnswers(
    [
      { question_id: "a", correct: true },
      { question_id: "a", correct: false },
      { question_id: "b", correct: false },
      { question_id: "c", correct: true },
      { question_id: "foundation", correct: false },
      { question_id: "unknown", correct: true },
      { question_id: "missing", correct: true },
    ],
    questions,
    blueprint.groups,
  );
  const issue = (group: number, id: number) =>
    result.issues_by_specialty[group - 1].issues.find(
      (i) => i.issue_id === id,
    )!;
  assert.equal(issue(1, 1).total, 2);
  assert.equal(issue(1, 1).correct, 1);
  assert.equal(assessmentPercent(issue(1, 1)), 50);
  assert.equal(assessmentPercent(issue(1, 2)), 0);
  assert.equal(assessmentPercent(issue(1, 3)), null);
  assert.equal(issue(2, 6).correct, 1);
  assert.equal(
    result.issues_by_specialty
      .flatMap((g) => g.issues)
      .reduce((sum, i) => sum + i.total, 0),
    4,
  );
  assert.equal(result.specialties[0].total, 4); // FND belongs to the group, never to a guessed issue.
  assert.equal(result.specialties[1].total, 1);
  assert.equal(result.issues_by_specialty.flatMap((g) => g.issues).length, 54);
});

test("an empty scope still includes every issue with unknown percentages", () => {
  const result = summarizeAnswers([], [], blueprint.groups);
  assert.ok(
    result.issues_by_specialty
      .flatMap((g) => g.issues)
      .every((i) => i.total === 0 && assessmentPercent(i) === null),
  );
});
