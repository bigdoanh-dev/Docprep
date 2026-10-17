import { Link } from "react-router-dom";
import { Bars, Heatmap, MemoryCurve } from "../../components/Charts";
import { LoadError, Loading } from "../../components/Status";
import { api, type ProgressRhythm as Rhythm } from "../../lib/api";
import {
  dayMonth,
  formatDate,
  formatTime,
  percent,
  studyTime,
} from "../../lib/format";
import { useLoad } from "../../lib/hooks";
import { LearningRhythm } from "../workspace/LearningRhythm";
import { Block, ProgressShell } from "./Progress";

const KIND: Record<Rhythm["activity"][number]["kind"], string> = {
  unit: "Học phần",
  practice: "Luyện tập",
  chat: "Hỏi đáp",
  cards: "Thẻ ôn",
  exam: "Thi thử",
};

// Tiến độ · Nhịp học (FR-LRN-14, 34): how the learner studies. Study time comes from the activity
// log, memory from the learner's own cards. The only forward-looking figures are what happens to
// memory without a review, and the cards already scheduled; nothing predicts the exam.
export function ProgressRhythm() {
  const { data, error, reload } = useLoad(
    () => api.get<Rhythm>("/progress/rhythm"),
    [],
  );
  // The cards the queue would serve now. The forecast's first bar also holds cards that come due
  // later today, which "Ôn thẻ" could not show yet.
  const dueNow = data?.memory.due_today ?? 0;
  return (
    <ProgressShell daysToExam={data?.days_to_exam}>
      {error && <LoadError message={error} onRetry={reload} />}
      {!data && !error && <Loading />}
      {data && (
        <>
          <LearningRhythm />
          <div className="row rhythm-summary" style={{ alignItems: "stretch" }}>
            <div className="card grow">
              <p className="muted small">Tuần này</p>
              <p style={{ fontSize: 24, fontWeight: 700 }}>
                {studyTime(data.week.minutes)}
              </p>
              <p className="muted small">
                Tuần trước: {studyTime(data.week.previous_minutes)}
              </p>
            </div>
            <div className="card grow">
              <p className="muted small">Ngày học</p>
              <p style={{ fontSize: 24, fontWeight: 700 }}>
                {data.week.study_days} / {data.week.days_elapsed}
              </p>
              <p className="muted small">ngày tuần này</p>
            </div>
          </div>

          <Block
            id="heat"
            title="Hoạt động 8 tuần"
            hint="Ô đậm hơn là học lâu hơn."
          >
            <Heatmap days={data.heatmap} label="8 tuần gần nhất" />
          </Block>

          <section className="card memory-curve-card stack" aria-labelledby="curve">
            <div>
              <h2 id="curve" className="h2">
                Khả năng nhớ
              </h2>
              <p className="muted small">Một thẻ bạn ôn nhiều nhất</p>
            </div>
            {data.curve.length === 0 ? (
              <p className="muted small">Ôn thẻ để xem biểu đồ.</p>
            ) : (
              <MemoryCurve points={data.curve} label="Khả năng nhớ theo thời gian" />
            )}
          </section>

          <Block id="memory" title="Trí nhớ">
            <div className="row" style={{ alignItems: "flex-start" }}>
              <div className="grow">
                <p style={{ fontSize: 24, fontWeight: 700 }}>
                  {percent(data.memory.recall_rate)}
                </p>
                <p className="muted small">nhớ đúng khi ôn</p>
                <p className="muted small">
                  {data.memory.window_days} ngày, {data.memory.reviews} lượt
                </p>
              </div>
              <div className="small" style={{ lineHeight: 1.9 }}>
                <div>
                  Mới · <b style={{ color: "var(--new)" }}>{data.memory.new}</b>
                </div>
                <div>
                  Đang học ·{" "}
                  <b style={{ color: "var(--learning-dark)" }}>
                    {data.memory.learning}
                  </b>
                </div>
                <div>
                  Đã thuộc ·{" "}
                  <b style={{ color: "var(--primary-dark)" }}>
                    {data.memory.mastered}
                  </b>
                </div>
              </div>
            </div>
          </Block>

          {data.recall_by_module.length > 0 && (
            <Block
              id="recall"
              title="Độ nhớ theo học phần"
              hint="Hiện tại → sau 7 ngày nếu chưa ôn"
            >
              {data.recall_by_module.map((m) => (
                <div key={m.module_id}>
                  <div className="row" style={{ marginBottom: 4 }}>
                    <span className="grow">{m.short_name}</span>
                    <span style={{ fontWeight: 600 }}>
                      {percent(m.now)} → {percent(m.in_7_days)}
                    </span>
                  </div>
                  {/* the whole bar is what is remembered now; the lighter end is what goes without a review */}
                  <div
                    className="progress"
                    style={{ height: 8, borderRadius: 4 }}
                  >
                    <span
                      style={{
                        width: `${m.now * 100}%`,
                        background: "var(--forget)",
                      }}
                    >
                      <span
                        style={{
                          display: "block",
                          height: "100%",
                          width: `${m.now > 0 ? Math.min(1, m.in_7_days / m.now) * 100 : 0}%`,
                          background: "var(--primary)",
                        }}
                      />
                    </span>
                  </div>
                </div>
              ))}
            </Block>
          )}

          <Block id="forecast" title="Thẻ đến hạn 7 ngày tới">
            <Bars
              label="Thẻ đến hạn 7 ngày tới"
              max={Math.max(1, ...data.due_forecast.map((d) => d.count))}
              items={data.due_forecast.map((d, i) => ({
                key: d.date,
                value: d.count,
                caption: String(d.count),
                label: i === 0 ? "Hôm nay" : dayMonth(d.date),
              }))}
            />
            {dueNow > 0 && (
              <Link to="/luyen-tap/on-the" className="btn primary block">
                Ôn {dueNow} thẻ hôm nay
              </Link>
            )}
          </Block>

          <Block id="activity" title="Hoạt động tuần này">
            {data.activity.length === 0 && (
              <p className="muted">Tuần này chưa có hoạt động nào.</p>
            )}
            {data.activity.map((a, i) => (
              <div
                key={i}
                className="row"
                style={{
                  alignItems: "flex-start",
                  borderTop: i ? "1px solid var(--divider)" : 0,
                  paddingTop: i ? 10 : 0,
                }}
              >
                <div className="grow">
                  <span className="tag">{KIND[a.kind]}</span>
                  <div style={{ fontWeight: 500, marginTop: 4 }}>{a.title}</div>
                  <div className="muted small">
                    {formatDate(a.occurred_at).slice(0, 5)} ·{" "}
                    {formatTime(a.occurred_at)}
                    {a.minutes != null ? ` · ${a.minutes} phút` : ""}
                  </div>
                </div>
                {a.result_vi && (
                  <span style={{ fontWeight: 600 }}>{a.result_vi}</span>
                )}
              </div>
            ))}
          </Block>
        </>
      )}
    </ProgressShell>
  );
}
