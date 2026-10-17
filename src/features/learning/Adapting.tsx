import { useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { AdaptationLines } from "../../components/AdaptationLines";
import { AiStar } from "../../components/AiStar";
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
      <div className="screen">
        <div className="body">
          <LoadError message={error} onRetry={reload} />
        </div>
      </div>
    );
  if (data === undefined)
    return (
      <div className="screen">
        <div className="body">
          <Loading />
        </div>
      </div>
    );
  if (data === null) return <Navigate to="/phien" replace />;

  const next = nextStep(data.session, "practice");
  const position = next
    ? data.session.steps.findIndex((s) => s.kind === next.kind) + 1
    : 0;
  const onDark = {
    background: "transparent",
    color: "#fff",
    borderColor: "var(--ink-3)",
  };
  return (
    <div className="screen" style={{ background: "var(--ink)", color: "#fff" }}>
      <div
        className="row"
        style={{
          justifyContent: "flex-end",
          minHeight: 60,
          padding: "8px 16px",
        }}
      >
        {!all && (
          <button
            className="btn"
            style={onDark}
            onClick={() => setShown(total)}
          >
            Bỏ qua
          </button>
        )}
      </div>
      <div className="body stack" style={{ padding: 24, gap: 16 }}>
        <AiStar size={40} onDark />
        <h1 className="title">Phần hỏi đáp đang điều chỉnh lộ trình của bạn</h1>
        <p style={{ color: "var(--primary-on-dark)" }}>
          Dựa trên {data.summary.graded.total} câu luyện điểm yếu bạn vừa làm
        </p>
        <div
          className="progress"
          style={{ background: "var(--ink-3)" }}
          role="progressbar"
          aria-label="Tiến trình điều chỉnh"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={all ? total : shown}
        >
          <span
            style={{
              width: `${total ? ((all ? total : shown) / total) * 100 : 100}%`,
              background: "var(--primary-on-dark)",
            }}
          />
        </div>
        <AdaptationLines
          summary={data.summary}
          shown={all ? undefined : shown}
          onDark
        />
      </div>
      {all && (
        <div className="stack" style={{ padding: "12px 16px 20px" }}>
          {next && (
            <Link to={stepPath(next)} className="btn primary lg block">
              Bước {position}: {STEP_LABEL[next.kind]}
            </Link>
          )}
          <Link to="/" className="btn lg block" style={onDark}>
            Dừng ở đây, về trang chủ
          </Link>
        </div>
      )}
    </div>
  );
}
