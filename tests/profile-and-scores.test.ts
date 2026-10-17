import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { LearnerProfilePanel } from "../src/features/workspace/LearnerProfilePanel.tsx";
import { ExamScoreHistory } from "../src/features/progress/ExamScoreHistory.tsx";
import type { Me, ProgressSkills } from "../src/lib/api.ts";

const me: Me = {
  pseudonym_id: "profile-test",
  display_name: "Test",
  audience: "graduate",
  organisation: "Cơ sở đào tạo A",
  focus_module_ids: [],
  exam_date: "2027-03-01",
  target_retention: 0.9,
  new_cards_per_day: 15,
  max_reviews_per_day: 100,
  diagnostic_prompt_dismissed: true,
};
function scoresHtml(scores: ProgressSkills["mock_scores"]) {
  return renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(ExamScoreHistory, { scores }),
    ),
  );
}

test("learner profile follows account audience and organisation without offering unsupported professions", () => {
  const graduate = renderToStaticMarkup(createElement(LearnerProfilePanel, { me }));
  assert.match(graduate, /Hồ sơ người học/);
  assert.match(graduate, /hai nhóm người học/);
  assert.match(graduate, /sinh viên Y học dự phòng năm cuối/);
  assert.match(graduate, /<dd>Đã tốt nghiệp<\/dd>/);
  assert.match(graduate, /Cơ sở đào tạo A/);
  assert.doesNotMatch(
    graduate,
    /Điều dưỡng|Y sĩ|Y học cổ truyền|răng hàm mặt|<input|<select|<button/,
  );
  const student = renderToStaticMarkup(
    createElement(LearnerProfilePanel, {
      me: { ...me, audience: "student", organisation: null },
    }),
  );
  assert.match(student, /<dd>Sinh viên<\/dd>/);
  assert.match(student, /Chưa có thông tin/);
});

test("attempts of the same exam retain distinct result routes, full dates and scores", () => {
  const html = scoresHtml([
    {
      attempt_id: 41,
      title: "Đề dịch tễ học",
      submitted_at: "2026-10-15T03:10:00Z",
      score: 1,
      total: 5,
    },
    {
      attempt_id: 42,
      title: "Đề dịch tễ học",
      submitted_at: "2026-10-16T03:10:00Z",
      score: 4,
      total: 5,
    },
  ]);
  assert.equal((html.match(/<h3>Đề dịch tễ học<\/h3>/g) ?? []).length, 2);
  assert.match(html, /href="\/thi-thu\/ket-qua\/41"/);
  assert.match(html, /href="\/thi-thu\/ket-qua\/42"/);
  assert.match(html, /dateTime="2026-10-15T03:10:00Z"/);
  assert.match(html, /dateTime="2026-10-16T03:10:00Z"/);
  assert.match(html, /15\/10\/2026/);
  assert.match(html, /16\/10\/2026/);
  assert.match(html, /1\/5/);
  assert.match(html, /4\/5/);
  assert.match(html, /aria-valuenow="20"/);
  assert.match(html, /aria-valuenow="80"/);
});

test("exam history distinguishes assessed zero, no graded questions, and no submitted attempts", () => {
  const score = {
    attempt_id: 3,
    title: "Đề thi thử",
    submitted_at: "2026-10-16T03:10:00Z",
    score: 0,
    total: 5,
  };
  assert.match(scoresHtml([score]), /aria-valuenow="0"/);
  const unknown = scoresHtml([{ ...score, total: 0 }]);
  assert.match(unknown, /Chưa có câu được chấm/);
  assert.doesNotMatch(unknown, /role="progressbar"/);
  assert.match(scoresHtml([]), /Chưa có bài thi đã nộp/);
});
