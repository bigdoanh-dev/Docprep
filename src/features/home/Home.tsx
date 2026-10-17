import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Layers,
  Route,
  Target,
} from "lucide-react";
import { Link } from "react-router-dom";
import { LearningActions } from "../../components/LearningActions";
import { DoctorAvatar } from "../../components/DoctorAvatar";
import { Loading, LoadError } from "../../components/Status";
import { api, type Home as HomeData, type SessionToday } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { useWorkspace } from "../../lib/learnerWorkspace";
import { stepPath, suggestionPath } from "../../lib/flow";
export function Home() {
  const w = useWorkspace();
  const { data, error, reload } = useLoad(async () => {
    const [home, today] = await Promise.all([
      api.get<HomeData>("/home"),
      api.get<SessionToday>("/session/today"),
    ]);
    return { home, today };
  }, []);
  if (error) return <LoadError message={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const { home, today } = data;
  const hour = new Date().getHours();
  const greeting =
    hour < 12
      ? "Chào buổi sáng"
      : hour < 18
        ? "Chào buổi chiều"
        : "Chào buổi tối";
  return (
    <div className="mobile-home">
      <section className="home-greeting">
        <div>
          <p>{greeting},</p>
          <h1>{home.name}</h1>
          <span>Học từng chút, vững kiến thức hơn.</span>
        </div>
        <DoctorAvatar gender={w.gender} />
      </section>
      <section className="due-summary">
        <div className="due-heading">
          <span className="feature-icon blue">
            <Layers size={26} />
          </span>
          <div>
            <h2>Thẻ ôn tập</h2>
            <p>
              <strong>{home.due_cards}</strong> thẻ đến hạn
            </p>
            <span>Ôn lại để nhớ lâu hơn.</span>
          </div>
        </div>
        <Link
          className="btn home-cta"
          to={home.due_cards ? "/luyen-tap/on-the" : "/luyen-tap/bo-the"}
        >
          {home.due_cards ? "Ôn thẻ ngay" : "Xem bộ thẻ"}
          <ArrowRight size={17} />
        </Link>
      </section>
      <LearningActions />
      <section className="today-section">
        <div className="section-head">
          <h2>Phiên học hôm nay</h2>
          <span>{today.total_minutes} phút</span>
        </div>
        <div className="today-list">
          {today.steps.map((s) => {
            const Icon =
              s.kind === "cards"
                ? Layers
                : s.kind === "practice"
                  ? Target
                  : BookOpen;
            return (
              <Link className="today-row" key={s.kind} to={stepPath(s)}>
                <span
                  className={`feature-icon ${s.kind === "cards" ? "blue" : s.kind === "practice" ? "amber" : "teal"}`}
                >
                  <Icon size={20} />
                </span>
                <div>
                  <strong>
                    {s.kind === "cards"
                      ? "Ôn thẻ đến hạn"
                      : s.kind === "practice"
                        ? "Luyện điểm yếu"
                        : "Học tiếp"}
                  </strong>
                  <span>
                    {s.done
                      ? "Đã hoàn thành"
                      : `${s.count} ${s.kind === "cards" ? "thẻ" : "câu"} · ${s.minutes} phút`}
                  </span>
                </div>
                {s.done ? (
                  <CheckCircle2 size={18} />
                ) : (
                  <ChevronRight size={18} />
                )}
              </Link>
            );
          })}
          {!today.steps.length && (
            <p className="muted">Bạn đã hoàn thành phiên hôm nay.</p>
          )}
        </div>
      </section>
      <section className="continue-section">
        <div className="section-head">
          <h2>Tiếp tục học</h2>
          <Link to="/luyen-tap">
            Tất cả <ChevronRight size={14} />
          </Link>
        </div>
        {home.recent
          .filter((r) => r.kind === "unit")
          .slice(0, 2)
          .map((r) => (
            <Link key={r.id} to={`/luyen-tap/${r.id}`} className="continue-row">
              <div>
                <h3>{r.title}</h3>
                <p>{r.subtitle_vi}</p>
                {r.progress !== null && (
                  <>
                    <div
                      className="progress"
                      role="progressbar"
                      aria-label={`Tiến độ ${r.title}`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(r.progress * 100)}
                    >
                      <span
                        style={{
                          width: `${Math.max(0, Math.min(1, r.progress)) * 100}%`,
                        }}
                      />
                    </div>
                    <small>{Math.round(r.progress * 100)}% hoàn thành</small>
                  </>
                )}
              </div>
              <ChevronRight size={18} />
            </Link>
          ))}
        {!home.recent.some((r) => r.kind === "unit") && (
          <Link className="list-row" to="/luyen-tap">
            Chọn học phần để bắt đầu <ChevronRight size={18} />
          </Link>
        )}
      </section>
      <div className="home-utilities" aria-label="Lối tắt học tập">
        <Link to="/lich-on">
          <CalendarDays size={16} strokeWidth={1.8} aria-hidden="true" />
          <span>Xem lịch ôn</span>
        </Link>
        <Link to="/lo-trinh">
          <Route size={16} strokeWidth={1.8} aria-hidden="true" />
          <span>Lộ trình học</span>
        </Link>
      </div>
      {home.tutor_suggestions.length > 0 && (
        <section className="home-suggestions">
          <h2>Gợi ý cho bạn</h2>
          {home.tutor_suggestions.map((s, i) => (
            <div key={i}>
              <p>{s.text_vi}</p>
              {s.action && (
                <Link to={suggestionPath(s.action)}>
                  {s.action.label_vi} <ArrowRight size={14} />
                </Link>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
