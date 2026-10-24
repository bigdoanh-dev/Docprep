import { useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { AdaptationLines } from "../../components/AdaptationLines";
import { LoadError, Loading } from "../../components/Status";
import { adaptationLines } from "../../lib/adaptation";
import {
  ApiError,
  api,
  type AdaptationSummary,
  type PracticeSetView,
  type SessionToday,
} from "../../lib/api";
import { STEP_LABEL, nextStep, stepPath } from "../../lib/flow";
import { useLoad } from "../../lib/hooks";

const LINE_MS = 700; // four lines at most: the reveal ends within 3 seconds

function TutorStar({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M12 2.5 14.75 9.25 21.5 12l-6.75 2.75L12 21.5l-2.75-6.75L2.5 12l6.75-2.75L12 2.5Z"
        fill="currentColor"
      />
    </svg>
  );
}

// Phần hỏi đáp đang điều chỉnh (FR-LRN-36): what the practice set just changed, line by line. Every line is
// a result the server returned for this set; a line it did not send is not shown. Skippable, and
// still when the learner asked for reduced motion.
export function Adapting() {
  const location = useLocation();
  const passed = (location.state as { summary?: AdaptationSummary } | null)
    ?.summary;
  const { data, error, reload } = useLoad(async () => {
    let summary = passed;
    if (!summary) {
      // Opened directly or reloaded. Only a set the learner has finished is asked for its summary:
      // asking would close an open one.
      try {
        const set = await api.get<PracticeSetView>("/session/today/practice");
        if (!set.completed) return null;
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
      summary = await api.post<AdaptationSummary>(
        "/session/today/practice/complete",
      );
    }
    return { summary, session: await api.get<SessionToday>("/session/today") };
  }, []);
  const [still] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [shown, setShown] = useState(0);
  const total = data ? adaptationLines(data.summary).length : 0;
  const all = still || shown >= total;

  useEffect(() => {
    if (!data || all) return;
    const timer = setTimeout(() => setShown((n) => n + 1), LINE_MS);
    return () => clearTimeout(timer);
  }, [data, all, shown]);

  if (error)
    return (
      <section className="adapting-screen">
        <div className="adapting-content adapting-state">
          <LoadError message={error} onRetry={reload} />
        </div>
      </section>
    );
  if (data === undefined)
    return (
      <section className="adapting-screen">
        <div className="adapting-content adapting-state">
          <Loading />
        </div>
      </section>
    );
  if (data === null) return <Navigate to="/phien" replace />;

  const next = nextStep(data.session, "practice");
  const position = next
    ? data.session.steps.findIndex((s) => s.kind === next.kind) + 1
    : 0;
  return (
    <section className="adapting-screen">
      <header className="adapting-topbar">
        <div className="adapting-brand">
          <TutorStar size={18} />
          <span>Gia sư AI</span>
        </div>
        {!all && (
          <button className="adapting-skip" onClick={() => setShown(total)}>
            Bỏ qua
          </button>
        )}
      </header>
      <main className="adapting-content">
        <div className="adapting-mark">
          <TutorStar size={30} />
        </div>
        <p className="adapting-kicker">Hoàn tất luyện điểm yếu</p>
        <h1 className="adapting-title">Gia sư đang điều chỉnh lộ trình học</h1>
        <p className="adapting-description">
          Dựa trên {data.summary.graded.total} câu luyện điểm yếu bạn vừa làm
        </p>
        <div className="adapting-progress-label">
          <span>Cập nhật lộ trình</span>
          <span>
            {all ? total : shown}/{total}
          </span>
        </div>
        <div
          className="adapting-progress"
          role="progressbar"
          aria-label="Tiến trình điều chỉnh"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={all ? total : shown}
        >
          <span
            style={{
              width: `${total ? ((all ? total : shown) / total) * 100 : 100}%`,
            }}
          />
        </div>
        <AdaptationLines
          summary={data.summary}
          shown={all ? undefined : shown}
          onDark
        />
      </main>
      {all && (
        <div className="adapting-actions">
          {next && (
            <Link to={stepPath(next)} className="btn primary block">
              Bước {position}: {STEP_LABEL[next.kind]}
            </Link>
          )}
          <Link to="/" className="btn block adapting-home-link">
            Dừng ở đây, về trang chủ
          </Link>
        </div>
      )}
    </section>
  );
}
