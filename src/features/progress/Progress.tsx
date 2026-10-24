import { useWorkspace } from "../../lib/learnerWorkspace";
import { SpecialtyAnalysis } from "./SpecialtyAnalysis";
import { useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { ShareBar } from "../../components/Charts";
import { LoadError, Loading } from "../../components/Status";
import { TabBar } from "../../components/TabBar";
import { api, type ProgressSkills } from "../../lib/api";
import { share } from "../../lib/charts";
import { ExamScoreHistory } from "./ExamScoreHistory";
import { useLoad } from "../../lib/hooks";

// The frame of both Tiến độ tabs: the title, the days left, and the switch between the two.
export function ProgressShell({
  daysToExam,
  children,
}: {
  daysToExam: number | undefined;
  children: ReactNode;
}) {
  const workspace = useWorkspace();
  const tab = ({ isActive }: { isActive: boolean }) =>
    `grow seg${isActive ? " active" : ""}`;
  return (
    <div className="screen mobile-progress">
      <div className="body stack" style={{ padding: 20, gap: 16 }}>
        <div className="progress-page-heading">
          <h1 className="title grow" style={{ fontSize: 26 }}>
            Thống kê học tập
          </h1>
          {workspace.examPeriod ? (
            <p className="muted small">Mục tiêu: {workspace.examPeriod}</p>
          ) : (
            daysToExam !== undefined && (
              <p className="muted small">
                Còn <b style={{ color: "var(--ink)" }}>{daysToExam} ngày</b> đến
                kỳ thi
              </p>
            )
          )}
        </div>
        <nav
          className="row"
          style={{ gap: 8 }}
          aria-label="Hai góc nhìn của Tiến độ"
        >
          <NavLink to="/tien-do" end className={tab}>
            Năng lực
          </NavLink>
          <NavLink to="/tien-do/nhip-hoc" className={tab}>
            Nhịp học
          </NavLink>
        </nav>
        {children}
      </div>
      <TabBar />
    </div>
  );
}

export function Block({
  id,
  title,
  hint,
  children,
}: {
  id: string;
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className="card stack" aria-labelledby={id}>
      <div>
        <h2 id={id} className="h2">
          {title}
        </h2>
        {hint && <p className="muted small">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

const SCOPES: { id: ProgressSkills["scope"]; label: string }[] = [
  { id: "latest3", label: "3 đề gần nhất" },
  { id: "all", label: "Tất cả" },
];

// Tiến độ · Năng lực (FR-LRN-13, 14): what the learner knows, counted from their own answers.
// Nothing here predicts the exam: no predicted score, pass line or trend (FR-LRN-26).
export function Progress() {
  const [scope, setScope] = useState<ProgressSkills["scope"]>("latest3");
  const { data, error, reload } = useLoad(
    () => api.get<ProgressSkills>(`/progress/skills?scope=${scope}`),
    [scope],
  );
  const [allModules, setAllModules] = useState(false);
  const modules = data
    ? allModules
      ? data.coverage.modules
      : data.coverage.modules.slice(0, 3)
    : [];

  return (
    <ProgressShell daysToExam={data?.days_to_exam}>
      {error && <LoadError message={error} onRetry={reload} />}
      {!data && !error && <Loading />}
      {data && (
        <>
          <div
            className="row"
            style={{ gap: 8 }}
            role="group"
            aria-label="Tính trên"
          >
            <span className="muted small">Tính trên</span>
            {SCOPES.map((s) => (
              <button
                key={s.id}
                className="pill"
                aria-pressed={scope === s.id}
                onClick={() => setScope(s.id)}
              >
                {s.label}
              </button>
            ))}
          </div>

          <p className="muted small">
            Xem mức độ đã luyện, chọn phần cần ôn rồi mở phân tích khi cần.
          </p>
          <Block id="coverage" title="Độ phủ chương trình">
            <p>
              <b style={{ fontSize: 24 }}>{data.coverage.assessed_topics}</b> /{" "}
              {data.coverage.total_topics} vấn đề cốt lõi đã luyện
            </p>
            <div className="progress" style={{ height: 8, borderRadius: 4 }}>
              <span
                style={{
                  width: `${share(data.coverage.assessed_topics, data.coverage.total_topics) * 100}%`,
                }}
              />
            </div>
            {modules.map((m) => (
              <ShareBar
                key={m.module_id}
                label={m.short_name}
                value={share(m.topics_assessed, m.topics_total)}
                text={`${m.topics_assessed}/${m.topics_total} chủ đề`}
              />
            ))}
            {data.coverage.modules.length > 3 && (
              <div>
                <button
                  className="link-btn"
                  onClick={() => setAllModules(!allModules)}
                >
                  {allModules
                    ? "Thu gọn"
                    : `Xem tất cả ${data.coverage.modules.length} học phần`}
                </button>
              </div>
            )}
          </Block>

          <Block id="priorities" title="Cần ưu tiên">
            {data.priorities.length === 0 && (
              <p className="muted">
                Chưa đủ dữ liệu. Hãy làm một bài luyện hoặc một đề thi thử.
              </p>
            )}
            {data.priorities.map((p) => (
              <div
                key={p.competency_code}
                className="row"
                style={{ alignItems: "flex-start" }}
              >
                <span
                  className="icon-box grey"
                  style={{ width: 32, height: 32, fontWeight: 600 }}
                >
                  {p.rank}
                </span>
                <div className="grow">
                  <div style={{ fontWeight: 600 }}>{p.name}</div>
                  <div className="muted small">
                    {p.correct}/{p.total} câu đúng
                    {p.weakest_vi ? ` · yếu nhất: ${p.weakest_vi}` : ""}
                  </div>
                </div>
                <Link
                  to={`/luyen-tap?hp=${p.module_id}`}
                  className="btn"
                  style={{ minHeight: 44 }}
                >
                  Luyện
                </Link>
              </div>
            ))}
          </Block>

          <details className="progress-details">
            <summary>Xem phân tích năng lực chi tiết</summary>
            <SpecialtyAnalysis
              specialties={data.specialties}
              levels={data.levels}
              bySpecialty={data.bloom_by_specialty}
            />
          </details>
          <Block
            id="scores"
            title="Điểm cả đề"
            hint="Kết quả từng lượt làm đã nộp trong phạm vi đang chọn."
          >
            <ExamScoreHistory scores={data.mock_scores} />
          </Block>
        </>
      )}
    </ProgressShell>
  );
}
