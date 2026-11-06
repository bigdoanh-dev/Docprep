import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Layers,
  MessageSquareText,
  Target,
  Timer,
} from "lucide-react";
import { Link } from "react-router-dom";
import { LearningActions } from "../../components/LearningActions";
import { DoctorAvatar } from "../../components/DoctorAvatar";
import { Loading, LoadError } from "../../components/Status";
import {
  api,
  type Home as HomeData,
  type ResumeItem,
  type SessionStep,
  type SessionToday,
} from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { useWorkspace } from "../../lib/learnerWorkspace";
import { nextStep, stepPath, suggestionPath, STEP_LABEL } from "../../lib/flow";
import { openTutor } from "../../lib/tutorLink";

// Trang chủ answers one question: what to do now. Top to bottom: today's session (its next step is
// the one main button, and due cards live there only), the one thing to pick up again, the tutor's
// suggestions with their reasons, then the shortcuts. The schedule and study plan are under Tiến độ.
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
  // The demo's payload has no resume item: its most recent unit stands in.
  const recent = home.recent.find((r) => r.kind === "unit");
  const resume: ResumeItem | null =
    home.resume !== undefined
      ? home.resume
      : recent
        ? {
            kind: "unit",
            id: recent.id,
            title: recent.title,
            subtitle_vi: recent.subtitle_vi ?? "",
            progress: recent.progress,
            path: `/luyen-tap/${recent.id}`,
          }
        : null;
  // Due cards are step 1 of today's session; the same advice again would only repeat it.
  const suggestions = home.tutor_suggestions.filter((s) => s.kind !== "cards");
  const topics = home.tutor_topics ?? [];
  return (
    <div className="mobile-home">
      <section
        className={`home-greeting${w.avatarUrl ? " has-custom-photo" : ""}`}
      >
        <div>
          <p>{greeting},</p>
          <h1>{home.name}</h1>
          <span>
            {typeof home.days_to_exam === "number"
              ? `Còn ${home.days_to_exam} ngày đến kỳ thi`
              : "Học từng chút, vững kiến thức hơn."}
          </span>
        </div>
        <DoctorAvatar gender={w.gender} />
      </section>

      <TodayCard today={today} />

      {resume && <ResumeRow item={resume} />}

      {(topics.length > 0 || suggestions.length > 0) && (
        <section className="home-suggestions">
          <h2>Gia sư gợi ý</h2>
          {topics.map((t) => (
            <div key={t.prompt}>
              <p>{t.reason_vi}</p>
              <button
                type="button"
                onClick={() => openTutor({ ask: t.prompt })}
              >
                <MessageSquareText size={14} aria-hidden="true" />
                Hỏi gia sư: {t.label_vi.toLocaleLowerCase("vi")}
                <ArrowRight size={14} />
              </button>
            </div>
          ))}
          {suggestions.map((s, i) => (
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

      <LearningActions />
    </div>
  );
}

const STEP_ICON = { cards: Layers, practice: Target, continue: BookOpen };
const STEP_TONE = { cards: "blue", practice: "amber", continue: "teal" };

function stepLine(s: SessionStep) {
  if (s.done) return "Đã hoàn thành";
  const unit =
    s.kind === "cards" ? "thẻ" : s.kind === "continue" ? "mục" : "câu";
  return `${s.count} ${unit} · ${s.minutes} phút`;
}

// Hôm nay: the steps, and one button for the next one not done.
function TodayCard({ today }: { today: SessionToday }) {
  const next = nextStep(today);
  const started = today.steps.some((s) => s.done);
  return (
    <section className="today-section" aria-labelledby="today-title">
      <div className="section-head">
        <h2 id="today-title">Phiên học hôm nay</h2>
        {next && <span>còn {today.total_minutes} phút</span>}
      </div>
      <div className="today-list">
        {today.steps.map((s) => {
          const Icon = STEP_ICON[s.kind];
          return (
            <Link className="today-row" key={s.kind} to={stepPath(s)}>
              <span className={`feature-icon ${STEP_TONE[s.kind]}`}>
                <Icon size={20} />
              </span>
              <div>
                <strong>{STEP_LABEL[s.kind]}</strong>
                <span>{stepLine(s)}</span>
              </div>
              {s.done ? <CheckCircle2 size={18} /> : <ChevronRight size={18} />}
            </Link>
          );
        })}
        {!today.steps.length && (
          <p className="muted">Hôm nay chưa có bước nào cần làm.</p>
        )}
      </div>
      {next ? (
        <Link className="btn primary block home-today-cta" to={stepPath(next)}>
          {started ? "Tiếp tục" : "Bắt đầu"}: {STEP_LABEL[next.kind]} · khoảng{" "}
          {next.minutes} phút
          <ArrowRight size={17} />
        </Link>
      ) : (
        today.steps.length > 0 && (
          <p className="home-today-done">
            <CheckCircle2 size={16} aria-hidden="true" /> Bạn đã xong phiên hôm
            nay.
          </p>
        )
      )}
    </section>
  );
}

const RESUME_ICON = {
  exam: Timer,
  unit: BookOpen,
  practice_set: ClipboardList,
  chat: MessageSquareText,
};

// Tiếp tục: the one unfinished thing touched last. A conversation opens in the tutor popup.
function ResumeRow({ item }: { item: ResumeItem }) {
  const Icon = RESUME_ICON[item.kind];
  const body = (
    <>
      <span className="feature-icon teal">
        <Icon size={20} />
      </span>
      <div>
        <h3>{item.title}</h3>
        <p>{item.subtitle_vi}</p>
        {item.progress !== null && (
          <div
            className="progress"
            role="progressbar"
            aria-label={`Tiến độ ${item.title}`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(item.progress * 100)}
          >
            <span
              style={{
                width: `${Math.max(0, Math.min(1, item.progress)) * 100}%`,
              }}
            />
          </div>
        )}
      </div>
      <ChevronRight size={18} />
    </>
  );
  return (
    <section className="continue-section" aria-labelledby="resume-title">
      <div className="section-head">
        <h2 id="resume-title">Tiếp tục</h2>
        <Link to="/luyen-tap">
          Học phần <ChevronRight size={14} />
        </Link>
      </div>
      {item.path ? (
        <Link to={item.path} className={`continue-row resume-${item.kind}`}>
          {body}
        </Link>
      ) : (
        <button
          type="button"
          className={`continue-row resume-${item.kind}`}
          onClick={() => openTutor({ session: Number(item.id) })}
        >
          {body}
        </button>
      )}
    </section>
  );
}
