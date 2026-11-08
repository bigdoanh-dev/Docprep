import blueprint from "../blueprint.json";
import { BLOOM, summarizeAnswers } from "../learningAnalytics";
import { progressQuestions } from "./progressExam";

export const ISSUE_DEMO_EXAM_ID = "issues-demo";
export const ISSUE_DEMO_EXAM_TITLE = "Đề thi demo · 54 vấn đề";

// Three variants each cover all 54 issues. Even the two-issue specialty covers
// all six Bloom levels across the three submitted demonstration attempts.
export const issueDemoQuestions = blueprint.groups.flatMap((group) =>
  group.issues.flatMap((issue, index) =>
    Array.from({ length: 3 }, (_, run) => {
      const level = ((index + run * 2) % 6) + 1;
      const template = progressQuestions.find(
        (q) => q.id === `q-progress-g${group.id}-b${level}`,
      )!;
      return {
        ...template,
        id: `q-issue-${issue.id}-b${level}`,
        competency_code: `CI-${issue.id}`,
        stem: `[Minh họa · ${group.short_name} · Vấn đề ${index + 1}: ${issue.name} · ${BLOOM[level - 1]}] ${template.stem.slice(template.stem.indexOf("] ") + 2)}`,
      };
    }),
  ),
);

export function issueExamQuestions(run = 0) {
  return blueprint.groups.flatMap((group) =>
    group.issues.map((issue, index) => {
      const level = ((index + run * 2) % 6) + 1;
      return issueDemoQuestions.find(
        (q) => q.id === `q-issue-${issue.id}-b${level}`,
      )!;
    }),
  );
}

export function createIssueDemoAttempts(startId: number, asOf: string) {
  return Array.from({ length: 3 }, (_, run) => {
    const questions = issueExamQuestions(run);
    const outcomes = questions.map((q) => {
      const issueId = Number(q.competency_code.slice(3));
      const outcome = (issueId + q.bloom_level + run) % 5;
      return {
        q,
        status: outcome === 0 ? "blank" : outcome === 1 ? "wrong" : "ok",
        chosen:
          outcome === 0
            ? null
            : q.options.find((o) => o.correct === outcome > 1)!.key,
      };
    });
    // Seed all samples at the migration instant so older real demo attempts
    // cannot displace a sample from the default “latest 3” analysis.
    const submittedAt = new Date(asOf).toISOString();
    const duration = (30 + run * 5) * 60;
    const attemptId = startId + run + 1;
    const title = `${ISSUE_DEMO_EXAM_TITLE} · Kết quả mẫu ${run + 1}`;
    const items = outcomes.map(({ q, status }, index) => ({
      n: index + 1,
      question_id: q.id,
      topic: blueprint.groups
        .flatMap((g) => g.issues)
        .find((i) => `CI-${i.id}` === q.competency_code)!.name,
      status,
    }));
    return {
      attempt_id: attemptId,
      form_id: ISSUE_DEMO_EXAM_ID,
      title,
      issue_demo_sample: true,
      questions: questions.map((q, index) => ({
        id: q.id,
        n: index + 1,
        stem: q.stem,
        options: q.options.map(({ key, text }) => ({ key, text })),
      })),
      answers: Object.fromEntries(
        outcomes
          .filter((o) => o.chosen !== null)
          .map((o) => [o.q.id, { chosen: o.chosen, flagged: false }]),
      ),
      started_at: new Date(
        Date.parse(submittedAt) - duration * 1000,
      ).toISOString(),
      deadline_at: new Date(Date.parse(submittedAt) + 3600000).toISOString(),
      submitted_at: submittedAt,
      warning_s: 300,
      results: {
        ...summarizeAnswers(
          items.map((i) => ({
            question_id: i.question_id,
            correct: i.status === "ok",
          })),
          issueDemoQuestions,
          blueprint.groups,
        ),
        attempt_id: attemptId,
        title,
        total: items.length,
        score: items.filter((i) => i.status === "ok").length,
        wrong: items.filter((i) => i.status === "wrong").length,
        blank: items.filter((i) => i.status === "blank").length,
        submitted_at: submittedAt,
        duration_s: duration,
        auto_submitted: false,
        new_cards: 0,
        priority_top: [
          ...new Set(
            items.filter((i) => i.status !== "ok").map((i) => i.topic),
          ),
        ].slice(0, 3),
        priority_moved_up: [],
        items,
      },
    };
  });
}
