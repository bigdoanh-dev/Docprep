import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import type { ProgressSkills } from "../../lib/api";
import { assessmentPercent } from "../../lib/learningAnalytics";
import { formatDate, formatTime } from "../../lib/format";

export function ExamScoreHistory({
  scores,
}: {
  scores: ProgressSkills["mock_scores"];
}) {
  if (!scores.length)
    return (
      <p className="muted">Chưa có bài thi đã nộp trong phạm vi đang chọn.</p>
    );
  return (
    <ol className="exam-score-history" aria-label="Kết quả từng lượt làm bài">
      {scores.map((s) => {
        const pct = assessmentPercent({ correct: s.score, total: s.total });
        return (
          <li key={s.attempt_id}>
            <h3>{s.title.trim() || "Bài thi đã nộp"}</h3>
            <p className="exam-score-meta">
              Lượt #{s.attempt_id} ·{" "}
              <time dateTime={s.submitted_at}>
                Nộp {formatDate(s.submitted_at)} lúc{" "}
                {formatTime(s.submitted_at)}
              </time>
            </p>
            {pct === null ? (
              <p className="muted small">Chưa có câu được chấm.</p>
            ) : (
              <>
                <div className="exam-score-numbers">
                  <span>
                    <strong>
                      {s.score}/{s.total}
                    </strong>{" "}
                    câu đúng
                  </span>
                  <strong>{pct}%</strong>
                </div>
                <div
                  className="progress"
                  role="progressbar"
                  aria-label={`Tỷ lệ câu đúng lượt ${s.attempt_id}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={pct}
                >
                  <span style={{ width: `${pct}%` }} />
                </div>
              </>
            )}
            <Link
              className="exam-score-link"
              to={`/thi-thu/ket-qua/${s.attempt_id}`}
              aria-label={`Xem kết quả lượt ${s.attempt_id}: ${s.title.trim() || "Bài thi đã nộp"}`}
            >
              Xem kết quả <ChevronRight size={16} aria-hidden="true" />
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
