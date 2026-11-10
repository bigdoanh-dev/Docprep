import test from "node:test";
import assert from "node:assert/strict";
import blueprint from "../src/lib/blueprint.json";
import {
  createIssueDemoAttempts,
  issueDemoQuestions,
  issueExamQuestions,
} from "../src/lib/demo/issueExam";
import {
  assessedExamAnswers,
  summarizeAnswers,
} from "../src/lib/learningAnalytics";

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

test("submitted samples assess answered items without treating blanks as wrong answers", () => {
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
    assert.equal(
      attempt.results.levels.reduce((sum, level) => sum + level.total, 0),
      Object.keys(attempt.answers).length,
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
    attempts.flatMap((a) => assessedExamAnswers(a.results.items)),
    issueDemoQuestions,
    blueprint.groups,
  );
  for (const group of summary.issues_by_specialty) {
    for (const issue of group.issues) {
      const answered = attempts
        .flatMap((a) => Object.keys(a.answers))
        .filter(
          (id) =>
            issueDemoQuestions.find((q) => q.id === id)?.competency_code ===
            `CI-${issue.issue_id}`,
        );
      assert.equal(issue.total, answered.length);
    }
  }
  assert.equal(
    summary.specialties.reduce((sum, s) => sum + s.total, 0),
    attempts.reduce((sum, a) => sum + Object.keys(a.answers).length, 0),
  );
});
