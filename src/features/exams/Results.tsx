import { SaveQuestion } from "../../components/SaveQuestion";
import { SpecialtyAnalysis } from "../progress/SpecialtyAnalysis";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CitationChip, useSourceSheet } from "../../components/Answer";
import { Icon } from "../../components/Icon";
import { LoadError, Loading } from "../../components/Status";
import { TabBar } from "../../components/TabBar";
import { TutorSheet } from "../../components/TutorSheet";
import {
  api,
  type ItemStatus,
  type Results as ResultsData,
  type ReviewItem,
} from "../../lib/api";
import { formatDate, formatDuration, formatTime } from "../../lib/format";
import { useLoad } from "../../lib/hooks";

type Filter = "all" | ItemStatus;
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "Tất cả" },
  { id: "wrong", label: "Sai" },
  { id: "blank", label: "Bỏ trống" },
  { id: "ok", label: "Đúng" },
];
const MARK: Record<
  ItemStatus,
  { sign: string; label: string; bg: string; fg: string }
> = {
  ok: {
    sign: "check",
    label: "đúng",
    bg: "var(--primary-tint)",
    fg: "var(--primary-dark)",
  },
  wrong: {
    sign: "close",
    label: "sai",
    bg: "var(--learning-tint)",
    fg: "var(--learning-dark)",
  },
  blank: {
    sign: "minus",
    label: "bỏ trống",
    bg: "var(--soft)",
    fg: "var(--text-2)",
  },
};
const LETTERS = ["A", "B", "C", "D", "E", "F"];

export function Results() {
  const { attemptId } = useParams();
  const { data, error, reload } = useLoad(
    () => api.get<ResultsData>(`/attempts/${attemptId}/results`),
    [attemptId],
  );
  const [filter, setFilter] = useState<Filter>("all");
  const rows =
    data?.items.filter((i) => filter === "all" || i.status === filter) ?? [];

  return (
    <div className="screen">
      <header className="topbar">
        <Link
          to="/thi-thu"
          className="icon-btn"
          aria-label="Quay lại danh sách đề"
        >
          <Icon name="left" />
        </Link>
        <h1>Kết quả{data ? ` · ${data.title}` : ""}</h1>
      </header>
      <div className="body stack">
        {error && <LoadError message={error} onRetry={reload} />}
        {!data && !error && <Loading />}
        {data && (
          <>
            <p className="learning-encouragement" role="status">
              {data.total > 0 && data.score === data.total
                ? "Bạn đã trả lời đúng tất cả câu hỏi trong lượt này. Hãy tiếp tục củng cố kiến thức ở chủ đề kế tiếp!"
                : "Bạn đã hoàn thành bài thi. Xem lại các câu cần củng cố và thử một lượt ôn ngắn để hiểu chắc hơn."}
            </p>
            <div className="card stack">
              <p>
                <span style={{ fontSize: 44, fontWeight: 700, lineHeight: 1 }}>
                  {data.score}
                </span>
                <span className="muted" style={{ fontSize: 18 }}>
                  {" "}
                  / {data.total} câu đúng
                </span>
              </p>
              <div className="row" style={{ alignItems: "stretch", gap: 8 }}>
                {[
                  ["Sai", String(data.wrong)],
                  ["Bỏ trống", String(data.blank)],
                  ["Thời gian", formatDuration(data.duration_s)],
                ].map(([k, v]) => (
                  <div
                    key={k}
                    className="grow"
                    style={{
                      background: "var(--bg)",
                      borderRadius: 12,
                      padding: "8px 10px",
                    }}
                  >
                    <div className="muted small">{k}</div>
                    <div style={{ fontWeight: 600 }}>{v}</div>
                  </div>
                ))}
              </div>
              <p className="muted small">
                Nộp lúc {formatTime(data.submitted_at)} ngày{" "}
                {formatDate(data.submitted_at)}
              </p>
              {data.auto_submitted && (
                <p className="note">Hết giờ nên bài được nộp tự động.</p>
              )}
            </div>

            {data.specialties && data.levels && (
              <SpecialtyAnalysis
                specialties={data.specialties}
                levels={data.levels}
                bySpecialty={data.bloom_by_specialty}
              />
            )}
            <div className="card tint" style={{ padding: 0 }}>
              <p className="label primary" style={{ padding: "14px 16px 4px" }}>
                Đã cập nhật ôn tập
              </p>
              <Link
                to="/tien-do"
                className="list-row"
                style={{ minHeight: 52 }}
              >
                <span className="grow">
                  {data.new_cards > 0 ? (
                    <>
                      <strong>+{data.new_cards} thẻ</strong> ôn từ câu sai
                    </>
                  ) : (
                    "Không có thẻ ôn mới"
                  )}
                </span>
                <Icon name="right" size={18} />
              </Link>
              <Link
                to="/luyen-tap"
                className="list-row"
                style={{
                  minHeight: 52,
                  borderTop: "1px solid rgba(30,122,79,0.18)",
                }}
              >
                <span className="grow">
                  Ưu tiên ôn: <strong>{data.priority_top.join(", ")}</strong>
                  {data.priority_moved_up.length > 0 && (
                    <span
                      className="small"
                      style={{ display: "block", color: "var(--primary-dark)" }}
                    >
                      Tăng ưu tiên sau bài này:{" "}
                      {data.priority_moved_up.join(", ")}
                    </span>
                  )}
                </span>
                <Icon name="right" size={18} />
              </Link>
            </div>

            <div
              className="row"
              style={{ gap: 8, overflowX: "auto" }}
              role="group"
              aria-label="Lọc câu hỏi"
            >
              {FILTERS.map((f) => (
                <button
                  key={f.id}
                  className="pill"
                  aria-pressed={filter === f.id}
                  onClick={() => setFilter(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
            {rows.length === 0 ? (
              <p className="empty">Không có câu nào trong nhóm này.</p>
            ) : (
              <div className="list">
                {rows.map((item) => (
                  <Link
                    key={item.question_id}
                    to={`/thi-thu/ket-qua/${attemptId}/${item.question_id}`}
                    className="list-row"
                  >
                    <span
                      style={{
                        width: 28,
                        height: 28,
                        flexShrink: 0,
                        borderRadius: 14,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 13,
                        fontWeight: 700,
                        background: MARK[item.status].bg,
                        color: MARK[item.status].fg,
                      }}
                    >
                      <span aria-hidden="true">
                        <Icon name={MARK[item.status].sign} size={16} />
                      </span>
                      <span className="sr">{MARK[item.status].label}</span>
                    </span>
                    <span className="grow">
                      <span style={{ display: "block", fontWeight: 500 }}>
                        Câu {item.n}
                      </span>
                      <span className="muted small">{item.topic}</span>
                    </span>
                    <span
                      style={{ color: "var(--primary-dark)", fontWeight: 500 }}
                    >
                      Xem lại
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      <TabBar />
    </div>
  );
}

export function AnswerReview() {
  const { attemptId, questionId } = useParams();
  const navigate = useNavigate();
  const base = `/thi-thu/ket-qua/${attemptId}`;
  const { data, error, reload } = useLoad(
    () =>
      Promise.all([
        api.get<ReviewItem>(`/attempts/${attemptId}/items/${questionId}`),
        api.get<ResultsData>(`/attempts/${attemptId}/results`),
      ]),
    [attemptId, questionId],
  );
  const [tutorOpen, setTutorOpen] = useState(false);
  const source = useSourceSheet();
  const [item, results] = data ?? [];
  const order = results?.items.map((i) => i.question_id) ?? [];
  const at = order.indexOf(questionId ?? "");
  const topic = results?.items[at]?.topic ?? "";
  const go = (delta: number) => {
    setTutorOpen(false);
    navigate(`${base}/${order[at + delta]}`);
  };

  return (
    <div className="screen">
      <header className="topbar">
        <Link to={base} className="icon-btn" aria-label="Quay lại kết quả">
          <Icon name="left" />
        </Link>
        <h1>Xem lại đáp án</h1>
      </header>
      <div className="body stack">
        {error && <LoadError message={error} onRetry={reload} />}
        {!data && !error && <Loading />}
        {item && (
          <>
            <p className="muted">
              Câu {item.n} / {item.total} · {topic}
            </p>
            <h2 className="title" style={{ fontSize: 19 }}>
              {item.stem}
            </h2>
            <SaveQuestion
              id={item.question_id}
              title={item.stem}
              detail={item.explanation}
              source={item.citations.map((c) => c.document).join("; ")}
            />
            {item.chosen === null && (
              <p className="note">Bạn bỏ trống câu này.</p>
            )}
            <div className="stack" style={{ gap: 10 }}>
              {item.options.map((o, i) => {
                const wrongPick = item.chosen === o.key && !o.is_correct;
                return (
                  <div
                    key={o.key}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      minHeight: 56,
                      padding: "10px 14px",
                      borderRadius: 14,
                      lineHeight: 1.4,
                      background: o.is_correct
                        ? "var(--primary-tint)"
                        : wrongPick
                          ? "var(--learning-tint)"
                          : "var(--surface)",
                      border: o.is_correct
                        ? "2px solid var(--primary)"
                        : wrongPick
                          ? "2px solid var(--learning)"
                          : "1px solid var(--border-input)",
                    }}
                  >
                    <span
                      aria-hidden="true"
                      style={{
                        width: 30,
                        height: 30,
                        flexShrink: 0,
                        borderRadius: 15,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 13,
                        fontWeight: 600,
                        background: "var(--soft)",
                      }}
                    >
                      {LETTERS[i]}
                    </span>
                    <span className="grow">{o.text}</span>
                    {o.is_correct && (
                      <span
                        style={{
                          color: "var(--primary-dark)",
                          fontWeight: 600,
                          fontSize: 13,
                          flexShrink: 0,
                        }}
                      >
                        <Icon name="check" size={15} /> Đáp án
                      </span>
                    )}
                    {wrongPick && (
                      <span
                        style={{
                          color: "var(--learning-dark)",
                          fontWeight: 600,
                          fontSize: 13,
                          flexShrink: 0,
                        }}
                      >
                        <Icon name="close" size={15} /> Bạn chọn
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="card stack">
              <p className="label">Giải thích của chuyên gia</p>
              <p style={{ fontSize: 16, color: "var(--text-2)" }}>
                {item.explanation}
              </p>
              {item.chosen &&
                item.rationales[item.chosen] &&
                !item.options.find((o) => o.key === item.chosen)
                  ?.is_correct && (
                  <p className="note">
                    Phương án bạn chọn: {item.rationales[item.chosen]}
                  </p>
                )}
              <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                {item.chosen !== null && (
                  <button className="btn" onClick={() => setTutorOpen(true)}>
                    Giải thích thêm
                  </button>
                )}
                {item.citations.map((c) => (
                  <CitationChip
                    key={c.passage_id}
                    citation={c}
                    onOpen={source.show}
                    label={c.page ? `tr. ${c.page}` : (c.article ?? "Nguồn")}
                  />
                ))}
              </div>
            </div>
          </>
        )}
      </div>
      {item && (
        <footer className="footer">
          <button
            className="btn grow"
            onClick={() => go(-1)}
            disabled={at <= 0}
          >
            Câu trước
          </button>
          <button
            className="btn grow"
            onClick={() => go(1)}
            disabled={at < 0 || at >= order.length - 1}
          >
            Câu sau
          </button>
        </footer>
      )}
      {item && (
        <TutorSheet
          key={item.question_id}
          open={tutorOpen}
          onClose={() => setTutorOpen(false)}
          questionId={item.question_id}
          topic={topic}
          onCite={source.show}
        />
      )}
      {source.sheet}
    </div>
  );
}
