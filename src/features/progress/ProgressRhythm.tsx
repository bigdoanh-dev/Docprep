import { Link } from "react-router-dom";
import { Bars, Heatmap, MemoryCurve } from "../../components/Charts";
import { LoadError, Loading } from "../../components/Status";
import { api, type ProgressRhythm as Rhythm } from "../../lib/api";
import {
  dayMonth,
  formatDate,
  formatTime,
  percent,
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

function readableStudyTime(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours === 0) return `${remainder} phút`;
  return remainder === 0
    ? `${hours} giờ`
    : `${hours} giờ ${remainder} phút`;
}

const WEEKDAY_SHORT = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

function todayInVietnam() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

function nextSevenDates(startDate: string) {
  const date = new Date(`${startDate}T12:00:00Z`);
  return Array.from({ length: 7 }, (_, index) => {
    date.setUTCDate(date.getUTCDate() + (index === 0 ? 0 : 1));
    const key = date.toISOString().slice(0, 10);
    return {
      key,
      label:
        index === 0
          ? "Hôm nay"
          : `${WEEKDAY_SHORT[date.getUTCDay()]}\n${dayMonth(key)}`,
    };
  });
}

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
  const forecastCounts = new Map(
    data?.due_forecast.map((day) => [day.date, day.count]) ?? [],
  );
  const forecastDays = data
    ? nextSevenDates(todayInVietnam()).map((day, index) => ({
        ...day,
        count: forecastCounts.get(day.key) ?? 0,
        isToday: index === 0,
      }))
    : [];
  const todayDueCount = forecastDays[0]?.count ?? 0;
  return (
    <ProgressShell daysToExam={data?.days_to_exam}>
      {error && <LoadError message={error} onRetry={reload} />}
      {!data && !error && <Loading />}
      {data && (
        <>
          <LearningRhythm />
          <section className="card rhythm-summary" aria-labelledby="rhythm-week">
            <div className="rhythm-summary-time">
              <h2 id="rhythm-week" className="muted small">
                Thời gian học tuần này
              </h2>
              <p className="rhythm-summary-total">
                {readableStudyTime(data.week.minutes)}
              </p>
              <p className="muted small">
                {data.week.minutes === data.week.previous_minutes
                  ? "Bằng tuần trước"
                  : `${data.week.minutes > data.week.previous_minutes ? "Nhiều hơn" : "Ít hơn"} tuần trước ${readableStudyTime(Math.abs(data.week.minutes - data.week.previous_minutes))}`}
              </p>
            </div>
            <div className="rhythm-summary-days">
              <div className="rhythm-summary-days-label">
                <span>Ngày có học</span>
                <strong>
                  {data.week.study_days}/{data.week.days_elapsed} ngày
                </strong>
              </div>
              <div
                className="rhythm-summary-bar"
                role="progressbar"
                aria-label={`${data.week.study_days} trên ${data.week.days_elapsed} ngày đã học tuần này`}
                aria-valuemin={0}
                aria-valuemax={data.week.days_elapsed}
                aria-valuenow={data.week.study_days}
              >
                <span
                  style={{
                    width: `${data.week.days_elapsed > 0 ? (data.week.study_days / data.week.days_elapsed) * 100 : 0}%`,
                  }}
                />
              </div>
              <p className="muted small">trong {data.week.days_elapsed} ngày đã qua</p>
            </div>
          </section>

          <Block
            id="heat"
            title="Lịch học 8 tuần qua"
            hint="Mỗi ô là một ngày. Màu đậm hơn nghĩa là bạn học lâu hơn."
          >
            <Heatmap days={data.heatmap} label="8 tuần gần nhất" />
          </Block>

          <Block id="memory" title="Kết quả ôn thẻ">
            <div className="row" style={{ alignItems: "flex-start" }}>
              <div className="grow">
                <p style={{ fontSize: 24, fontWeight: 700 }}>
                  {percent(data.memory.recall_rate)}
                </p>
                <p className="muted small">trả lời đúng khi ôn</p>
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

          <section className="card memory-curve-card stack" aria-labelledby="curve">
            <div>
              <h2 id="curve" className="h2">
                Độ nhớ của một thẻ
              </h2>
              <p className="muted small">Thẻ bạn ôn nhiều nhất</p>
            </div>
            {data.curve.length === 0 ? (
              <p className="muted small">Ôn thẻ để xem biểu đồ.</p>
            ) : (
              <MemoryCurve points={data.curve} label="Độ nhớ của thẻ theo thời gian" />
            )}
          </section>

          {data.recall_by_module.length > 0 && (
            <Block
              id="recall"
              title="Độ nhớ theo học phần"
              hint="So sánh mức nhớ hiện tại với dự kiến sau 7 ngày nếu chưa ôn lại."
            >
              <div className="recall-module-list">
                {data.recall_by_module.map((m) => {
                  const now = Math.min(1, Math.max(0, m.now));
                  const later = Math.min(1, Math.max(0, m.in_7_days));
                  const remembered = Math.min(now, later);
                  const change = Math.abs(now - later);
                  const outside = Math.max(0, 1 - Math.max(now, later));
                  return (
                    <article className="recall-module" key={m.module_id}>
                      <h3>{m.short_name}</h3>
                      <div className="recall-module-values">
                        <div>
                          <span>Hiện tại</span>
                          <strong>{percent(m.now)}</strong>
                        </div>
                        <div>
                          <span>Sau 7 ngày nếu chưa ôn</span>
                          <strong>{percent(m.in_7_days)}</strong>
                        </div>
                      </div>
                      <div
                        className="recall-range"
                        role="img"
                        aria-label={`${m.short_name}: hiện tại ${percent(m.now)}, dự kiến ${percent(m.in_7_days)} sau 7 ngày nếu chưa ôn`}
                      >
                        <span
                          className="recall-range-remembered"
                          style={{ width: `${remembered * 100}%` }}
                        />
                        <span
                          className="recall-range-change"
                          style={{ width: `${change * 100}%` }}
                        />
                        <span
                          className="recall-range-outside"
                          style={{ width: `${outside * 100}%` }}
                        />
                      </div>
                    </article>
                  );
                })}
              </div>
              <ul className="recall-legend" aria-label="Chú giải biểu đồ độ nhớ">
                <li><span className="remembered" />Mức nhớ dự kiến</li>
                <li><span className="change" />Phần có thể giảm</li>
              </ul>
            </Block>
          )}

          <Block
            id="forecast"
            title="Lịch thẻ cần ôn"
            hint="Số thẻ đến hạn mỗi ngày trong 7 ngày tới."
          >
            <div className="due-forecast-today">
              <span>Hôm nay</span>
              <strong>{todayDueCount}</strong>
              <span>thẻ đến hạn</span>
            </div>
            <div className="due-forecast-chart">
              <Bars
                label="Số thẻ đến hạn theo ngày trong 7 ngày tới"
                max={Math.max(1, ...forecastDays.map((day) => day.count))}
                items={forecastDays.map((day) => ({
                  key: day.key,
                  value: day.count,
                  caption: String(day.count),
                  label: day.label,
                  isToday: day.isToday,
                  color: day.isToday ? "var(--primary)" : "#8fb5ea",
                }))}
              />
            </div>
            {dueNow > 0 && (
              <Link to="/luyen-tap/on-the" className="btn primary block">
                Mở hàng đợi ôn tập
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
