import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Sheet } from "../../components/Sheet";
import { LoadError, Loading } from "../../components/Status";
import { TabBar } from "../../components/TabBar";
import {
  api,
  type AttemptView,
  type ExamForm,
  type ExamPlan,
  type Listed,
} from "../../lib/api";
import { formatDate, formatDuration, formatTime, mmss } from "../../lib/format";
import { useLoad } from "../../lib/hooks";

// "5 câu mới · 3 câu từng sai · 2 câu ôn lại", leaving out empty groups
function mixLine(plan: ExamPlan): string {
  const { composition: c } = plan;
  return [
    [c.new, "câu mới"],
    [c.wrong, "câu từng sai"],
    [c.review, "câu ôn lại"],
  ]
    .filter(([n]) => (n as number) > 0)
    .map(([n, label]) => `${n} ${label}`)
    .join(" · ");
}

function meta(form: ExamForm): string {
  const left =
    form.attempts_left === null ? "" : ` · còn ${form.attempts_left} lượt`;
  return `${form.n_questions} câu · ${form.minutes} phút${left}`;
}

export function Exams() {
  const { data, error, reload } = useLoad(
    () => api.get<Listed<ExamForm>>("/exams"),
    [],
  );
  return (
    <div className="screen">
      <div className="body stack" style={{ padding: 20 }}>
        <h1 className="title" style={{ fontSize: 26, marginTop: 12 }}>
          Thi thử
        </h1>
        {error && <LoadError message={error} onRetry={reload} />}
        {!data && !error && <Loading />}
        {data?.items.length === 0 && (
          <p className="empty">Chưa có đề thi thử.</p>
        )}
        {data?.items
          .toSorted(
            (a, b) =>
              Number(b.open_attempt_id !== null) -
                Number(a.open_attempt_id !== null) ||
              Number(a.kind === "diagnostic" && a.history.length > 0) -
                Number(b.kind === "diagnostic" && b.history.length > 0),
          )
          .map((form) => (
            <FormCard key={form.id} form={form} />
          ))}
      </div>
      <TabBar />
    </div>
  );
}

function FormCard({ form }: { form: ExamForm }) {
  const navigate = useNavigate();
  const running = form.open_attempt_id !== null;
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string>();

  // "Làm bài mới" while an attempt is running: the server hands that one in and opens a new one.
  const startFresh = async () => {
    setStarting(true);
    setStartError(undefined);
    try {
      const attempt = await api.post<AttemptView>(
        `/exams/${form.id}/attempts`,
        { fresh: true },
      );
      navigate(`/thi-thu/lam-bai/${attempt.attempt_id}`);
    } catch (e) {
      setStartError((e as Error).message);
      setStarting(false);
    }
  };

  return (
    <section className="card stack" aria-label={form.title}>
      <div>
        <h2 className="h2" style={{ fontSize: 17 }}>
          {form.title}
        </h2>
        {form.kind === "diagnostic" && (
          <span className="tag" style={{ margin: "4px 0" }}>
            Đánh giá năng lực
          </span>
        )}
        {form.kind === "mock" && form.history.length === 0 && !running && (
          <span className="tag" style={{ margin: "4px 0" }}>
            Mới
          </span>
        )}
        <p className="tag exam-state">
          {running
            ? "Đang làm"
            : form.history.length
              ? `✓ Đã hoàn thành · ${form.history.length} lượt`
              : "Chưa làm"}
        </p>
        <p className="muted">{meta(form)}</p>
        {form.kind === "diagnostic" && (
          <p className="muted small">
            Kết quả sẽ cập nhật bộ thẻ và chủ đề cần ôn.
          </p>
        )}
        {form.plan && !running && (
          <p
            className="small"
            style={{ color: "var(--primary-dark)", marginTop: 4 }}
          >
            Ráp riêng cho bạn · lần tới: {mixLine(form.plan)}
          </p>
        )}
      </div>

      {running ? (
        <>
          <p className="warn">
            Bạn đang làm dở đề này · còn {mmss(form.open_remaining_s ?? 0)}.
            Đồng hồ vẫn chạy.
          </p>
          <Link
            to={`/thi-thu/lam-bai/${form.open_attempt_id}`}
            className="btn primary block"
          >
            Làm tiếp
          </Link>
          <button
            className="btn block"
            onClick={() => setConfirmOpen(true)}
            disabled={form.attempts_left === 0}
          >
            Làm bài mới
          </button>
        </>
      ) : (
        <Link
          to={`/thi-thu/${form.id}/quy-dinh`}
          className={`btn block ${form.history.length ? "" : "primary"}`}
        >
          {form.history.length
            ? "Làm bài mới"
            : form.kind === "diagnostic"
              ? "Làm bài đánh giá"
              : "Bắt đầu làm bài"}
        </Link>
      )}

      <Sheet
        open={confirmOpen}
        onClose={() => !starting && setConfirmOpen(false)}
        title="Làm bài mới?"
      >
        <div className="stack">
          <p style={{ fontSize: 16 }}>
            Bài đang làm dở sẽ được nộp với những câu bạn đã trả lời và lưu vào
            lịch sử. Sau đó bài mới bắt đầu ngay, đồng hồ tính lại từ đầu.
          </p>
          {startError && (
            <p className="warn" role="alert">
              {startError}
            </p>
          )}
          <button
            className="btn primary block"
            onClick={startFresh}
            disabled={starting}
          >
            {starting ? "Đang mở bài…" : "Nộp và làm bài mới"}
          </button>
          <button
            className="btn block"
            onClick={() => setConfirmOpen(false)}
            disabled={starting}
          >
            Quay lại
          </button>
        </div>
      </Sheet>

      {form.history.length > 0 && (
        <div className="stack" style={{ gap: 6 }}>
          <h3 className="label">Lịch sử làm bài</h3>
          <div className="list">
            {form.history.map((h) => (
              <Link
                key={h.attempt_id}
                to={`/thi-thu/ket-qua/${h.attempt_id}`}
                className="list-row"
                aria-label={`Lượt làm ngày ${formatDate(h.submitted_at)} lúc ${formatTime(h.submitted_at)}, ${h.score} trên ${h.total} câu đúng. Xem kết quả`}
              >
                <span className="grow">
                  <span style={{ display: "block", fontWeight: 500 }}>
                    {formatDate(h.submitted_at)} · {formatTime(h.submitted_at)}
                  </span>
                  <span className="muted small">
                    Làm trong {formatDuration(h.duration_s)}
                    {h.auto_submitted ? " · hết giờ, tự nộp" : ""}
                  </span>
                </span>
                <span style={{ textAlign: "right", flexShrink: 0 }}>
                  <span style={{ display: "block", fontWeight: 600 }}>
                    {h.score}/{h.total}
                  </span>
                  <span className="muted small">câu đúng</span>
                </span>
                <Icon name="right" size={18} />
              </Link>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

const RULES = [
  "Không tạm dừng được",
  "Tự lưu sau mỗi câu",
  "Quay lại câu trước được",
  "Hết giờ sẽ tự nộp bài",
];

export function ExamRules() {
  const { formId } = useParams();
  const navigate = useNavigate();
  const { data, error, reload } = useLoad(
    () => api.get<Listed<ExamForm>>("/exams"),
    [],
  );
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string>();
  const form = data?.items.find((f) => f.id === formId);
  const running = form ? form.open_attempt_id !== null : false;

  const start = async () => {
    setStarting(true);
    setStartError(undefined);
    try {
      // When an attempt is still running the server returns it, so this also resumes.
      const attempt = await api.post<AttemptView>(`/exams/${formId}/attempts`);
      navigate(`/thi-thu/lam-bai/${attempt.attempt_id}`, { replace: true });
    } catch (e) {
      setStartError((e as Error).message);
      setStarting(false);
    }
  };

  return (
    <div className="screen">
      <header className="topbar">
        <Link to="/thi-thu" className="icon-btn" aria-label="Quay lại">
          <Icon name="left" />
        </Link>
        <h1>Quy định đề thi thử</h1>
      </header>
      <div className="body stack" style={{ padding: 20 }}>
        {error && <LoadError message={error} onRetry={reload} />}
        {!data && !error && <Loading />}
        {data && !form && <LoadError message="Không tìm thấy đề thi." />}
        {form && (
          <>
            <h2 className="title">{form.title}</h2>
            {running && (
              <p className="warn">
                Bạn đang làm dở đề này · còn {mmss(form.open_remaining_s ?? 0)}.
                Đồng hồ vẫn chạy.
              </p>
            )}
            {form.plan && !running && (
              <section
                className="card tint stack"
                style={{ gap: 8 }}
                aria-label="Đề lần này"
              >
                <h3 className="label primary">Đề lần này</h3>
                <p style={{ fontWeight: 600 }}>{mixLine(form.plan)}</p>
                <p className="small" style={{ color: "var(--text-2)" }}>
                  {form.plan.topics
                    .map((t) => `${t.name} ${t.count}`)
                    .join(" · ")}
                </p>
                <p className="small muted">
                  Đề được ráp từ kết quả các bài trước, nội dung bạn đã học xong
                  và mức độ nắm từng chủ đề. Chủ đề còn yếu hoặc đã học xong có
                  nhiều câu hơn.
                </p>
              </section>
            )}
            <div className="row" style={{ alignItems: "stretch" }}>
              <div className="card grow">
                <div className="title" style={{ fontSize: 28 }}>
                  {form.n_questions}
                </div>
                <div className="muted">câu hỏi</div>
              </div>
              <div className="card grow">
                <div className="title" style={{ fontSize: 28 }}>
                  {form.minutes}
                </div>
                <div className="muted">phút cho cả đề</div>
              </div>
            </div>
            <ul
              className="list"
              style={{ listStyle: "none", margin: 0, padding: 0 }}
            >
              {RULES.map((rule) => (
                <li key={rule} className="list-row" style={{ minHeight: 52 }}>
                  <span style={{ color: "var(--primary)" }}>
                    <Icon name="check" size={20} />
                  </span>
                  {rule}
                </li>
              ))}
            </ul>
            {form.attempts_left !== null && (
              <p className="note">Còn {form.attempts_left} lượt làm đề này</p>
            )}
            {startError && (
              <p className="warn" role="alert">
                {startError}
              </p>
            )}
          </>
        )}
      </div>
      {form && (
        <footer className="footer">
          <button
            className="btn primary lg block"
            onClick={start}
            disabled={starting || (!running && form.attempts_left === 0)}
          >
            {starting ? "Đang mở đề…" : running ? "Làm tiếp" : "Bắt đầu"}
          </button>
        </footer>
      )}
    </div>
  );
}
