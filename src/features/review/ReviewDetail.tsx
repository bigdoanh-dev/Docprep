import { ArrowLeft, BookOpen, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useActor } from "../../app/identity";
import { Sheet } from "../../components/Sheet";
import { LoadError, Loading } from "../../components/Status";
import { useFeedback } from "../../components/ui/Feedback";
import { api } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { statusName } from "./status";
export function ReviewDetail({ id }: { id: string }) {
  const actor = useActor()!,
    notify = useFeedback(),
    navigate = useNavigate();
  const { data, error, reload } = useLoad(
    () => api.get<any>(`/review/items/${id}`),
    [id],
  );
  const [decision, setDecision] = useState(""),
    [comment, setComment] = useState(""),
    [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  if (error) return <LoadError message={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const round = data.status === "in_review_r2" ? 2 : 1,
    closed = !["in_review_r1", "in_review_r2"].includes(data.status),
    sameReviewer =
      round === 2 &&
      data.decisions.some((d: any) => d.round === 1 && d.reviewer === actor.id);
  const submit = async () => {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      const result = await api.post<any>(`/review/items/${id}/decisions`, {
        version: data.version,
        round,
        decision,
        comment: comment.trim() || null,
      });
      notify(
        `${actor.mode === "demo" ? "Đã ghi nhận quyết định minh họa" : "Đã gửi quyết định"}: ${statusName[result.status] ?? result.status}.`,
      );
      setConfirm(false);
      navigate("/tham-dinh");
    } catch (e) {
      setNotice((e as Error).message);
      notify((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="review-detail">
      <header className="page-heading">
        <h1>Bàn thẩm định</h1>
        <p>Kiểm tra nội dung, đối chiếu bằng chứng.</p>
      </header>
      <Link to="/tham-dinh" className="back-link">
        <ArrowLeft size={16} />
        Quay lại danh sách
      </Link>
      <div className="review-columns">
        <section className="panel stack">
          <div className="row">
            <strong>Câu hỏi {id}</strong>
            <span className="status-tag">
              Vòng {round} · phiên bản {data.version}
            </span>
          </div>
          <div className="meta-line">
            <span>Mã năng lực: {data.competency_code}</span>
            <span>Mức độ câu hỏi: {data.bloom_level ?? "Chưa gán"}</span>
            <span>Độ khó: {data.difficulty_label ?? "Chưa gán"}</span>
          </div>
          {data.ai_assisted && (
            <p className="notice small">
              Bản nháp có AI hỗ trợ. AI không quyết định phê duyệt.
            </p>
          )}
          <h2>{data.stem ?? data.body}</h2>
          <div className="review-options">
            {data.options.map((o: any) => (
              <div key={o.key} className={o.is_correct ? "correct" : ""}>
                <strong>
                  {o.key.toUpperCase()}. {o.text}
                </strong>
                {o.is_correct && (
                  <span>
                    <CheckCircle2 size={16} />
                    Đáp án đúng
                  </span>
                )}
                <p>{o.rationale}</p>
              </div>
            ))}
          </div>
          <section className="expert-explanation">
            <h3>Giải thích đáp án</h3>
            <p>{data.explanation}</p>
          </section>
        </section>
        <aside className="review-source">
          <section className="panel stack">
            <h2>
              <BookOpen size={21} />
              Nguồn đối chiếu
            </h2>
            {data.passages.map((p: any) => (
              <div className="source-paper" key={p.id}>
                <h3>{p.document}</h3>
                <p className="muted small">
                  {p.chapter} · trang {p.page}
                </p>
                <p className="reading">{p.excerpt}</p>
                <p className="notice small">{p.demo_label}</p>
              </div>
            ))}
          </section>
          <section className="panel">
            <h3>Các quyết định trước đây</h3>
            {!data.decisions.length ? (
              <p className="muted">Chưa có quyết định.</p>
            ) : (
              data.decisions.map((d: any, i: number) => (
                <div className="timeline-entry" key={i}>
                  <strong>
                    Vòng {d.round}:{" "}
                    {d.decision === "pass"
                      ? "Đạt"
                      : d.decision === "revise"
                        ? "Cần sửa"
                        : "Loại"}
                  </strong>
                  <small>
                    {d.reviewer} ·{" "}
                    {new Date(d.created_at).toLocaleString("vi-VN")}
                  </small>
                  <p>{d.comment ?? "Không có nhận xét bổ sung."}</p>
                </div>
              ))
            )}
          </section>
        </aside>
      </div>
      <form
        className="decision-panel"
        onSubmit={(e) => {
          e.preventDefault();
          setConfirm(true);
        }}
      >
        <div>
          <h3>Quyết định vòng {round}</h3>
          <div className="decision-options">
            {[
              ["pass", "Đạt"],
              ["revise", "Cần sửa"],
              ["reject", "Loại"],
            ].map(([value, label]) => (
              <label
                className={decision === value ? "selected" : ""}
                key={value}
              >
                <input
                  type="radio"
                  name="decision"
                  value={value}
                  checked={decision === value}
                  onChange={() => setDecision(value)}
                  disabled={closed || sameReviewer}
                />
                {label}
              </label>
            ))}
          </div>
        </div>
        <label className="field grow">
          Nhận xét {decision !== "pass" ? "(bắt buộc)" : "(không bắt buộc)"}
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            maxLength={2000}
            placeholder="Nêu lý do, phần cần sửa và nguồn đối chiếu…"
          />
        </label>
        <button
          className="btn primary"
          disabled={
            closed ||
            sameReviewer ||
            !decision ||
            (decision !== "pass" && !comment.trim()) ||
            busy
          }
        >
          Gửi quyết định
        </button>
      </form>
      {sameReviewer && (
        <p className="warn" role="alert">
          Bạn đã duyệt vòng 1. Vòng 2 phải do chuyên gia khác thực hiện.
        </p>
      )}
      {closed && (
        <p className="notice">
          Mục không còn ở trạng thái chờ duyệt. Muốn sửa nội dung đã duyệt cần
          tạo phiên bản mới.
        </p>
      )}
      <Sheet
        open={confirm}
        onClose={() => !busy && setConfirm(false)}
        title="Xác nhận quyết định"
      >
        <div className="stack">
          <p>
            Gửi quyết định{" "}
            <strong>
              {decision === "pass"
                ? "Đạt"
                : decision === "revise"
                  ? "Cần sửa"
                  : "Loại"}
            </strong>{" "}
            cho {id}, phiên bản {data.version}, vòng {round}.
          </p>
          <p>{comment || "Không có nhận xét bổ sung."}</p>
          {actor.mode === "demo" && (
            <p className="notice">
              Chỉ ghi quyết định minh họa trên trình duyệt, không phải phê duyệt
              chuyên môn thật.
            </p>
          )}
          {notice && (
            <p className="warn" role="alert">
              {notice}
            </p>
          )}
          <button className="btn primary" onClick={submit} disabled={busy}>
            {busy ? "Đang gửi…" : "Xác nhận gửi"}
          </button>
          <button
            className="btn"
            onClick={() => setConfirm(false)}
            disabled={busy}
          >
            Quay lại chỉnh
          </button>
        </div>
      </Sheet>
    </div>
  );
}
