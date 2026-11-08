import test from "node:test";
import assert from "node:assert/strict";
import blueprint from "../src/lib/blueprint.json";
import {
  createIssueDemoAttempts,
  issueDemoQuestions,
  issueExamQuestions,
} from "../src/lib/demo/issueExam";
import { summarizeAnswers } from "../src/lib/learningAnalytics";

test("each demo exam contains all 54 issues once with unique question IDs", () => {
  assert.equal(
    new Set(issueDemoQuestions.map((q) => q.id)).size,
    issueDemoQuestions.length,
  );
  for (let run = 0; run < 3; run++) {
    const questions = issueExamQuestions(run);
    assert.equal(questions.length, 54);
    assert.equal(new Set(questions.map((q) => q.id)).size, 54);
    assert.equal(new Set(questions.map((q) => q.competency_code)).size, 54);
    assert.ok(
      questions.every((q) => q.options.filter((o) => o.correct).length === 1),
    );
  }
});

test("three submitted samples populate all issues and every specialty × Bloom cell", () => {
  const attempts = createIssueDemoAttempts(100, "2026-11-05T08:00:00.000Z");
  assert.deepEqual(
    attempts.map((a) => a.attempt_id),
    [101, 102, 103],
  );
  for (const attempt of attempts) {
    assert.equal(attempt.results.total, 54);
    assert.equal(
      attempt.results.score + attempt.results.wrong + attempt.results.blank,
      54,
    );
    assert.ok(
      attempt.results.score > 0 &&
        attempt.results.wrong > 0 &&
        attempt.results.blank > 0,
    );
    for (const item of attempt.results.items) {
      const q = issueDemoQuestions.find((q) => q.id === item.question_id)!;
      const chosen = attempt.answers[q.id]?.chosen;
      assert.equal(
        item.status,
        !chosen
          ? "blank"
          : q.options.find((o) => o.key === chosen)!.correct
            ? "ok"
            : "wrong",
      );
    }
  }
  const summary = summarizeAnswers(
    attempts.flatMap((a) =>
      a.results.items.map((i) => ({
        question_id: i.question_id,
        correct: i.status === "ok",
      })),
    ),
    issueDemoQuestions,
    blueprint.groups,
  );
  assert.ok(
    summary.issues_by_specialty.every((g) =>
      g.issues.every((i) => i.total === 3),
    ),
  );
  assert.ok(
    summary.bloom_by_specialty.every((g) => g.levels.every((l) => l.total > 0)),
  );
  assert.equal(
    summary.specialties.reduce((sum, s) => sum + s.total, 0),
    162,
  );
});
