import { CalendarDays } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { LoadError, Loading } from "../../components/Status";
import { api, type ProgressRhythm } from "../../lib/api";
import { localDay } from "../../lib/learnerWorkspace";
import { useLoad } from "../../lib/hooks";

export function Calendar() {
  const { data, error, reload } = useLoad(
    () => api.get<ProgressRhythm>("/progress/rhythm"),
    [],
  );
  const today = localDay();
  const [month, setMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const [selected, setSelected] = useState(today);
  const offset = (month.getDay() + 6) % 7;
  const total = new Date(
    month.getFullYear(),
    month.getMonth() + 1,
    0,
  ).getDate();
  const selectedDue =
    data?.due_forecast.find((day) => day.date === selected)?.count ?? 0;
  const learned =
    data?.heatmap.find((day) => day.date === selected)?.minutes ?? 0;
  const label = (date: string) =>
    new Date(`${date}T12:00:00`).toLocaleDateString("vi-VN");
  function moveMonth(delta: number) {
    const next = new Date(month.getFullYear(), month.getMonth() + delta, 1);
    setMonth(next);
    setSelected(
      `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-01`,
    );
  }
  return (
    <div className="calendar-page">
      <header className="page-heading">
        <h1>Lịch ôn tập</h1>
        <p>Chọn ngày để xem thẻ đến hạn và thời gian đã học.</p>
      </header>
      {error && <LoadError message={error} onRetry={reload} />}
      {!data && !error && <Loading />}
      <div className="calendar-layout">
        <section className="panel">
          <div className="section-head">
            <h2>
              {month.toLocaleDateString("vi-VN", {
                month: "long",
                year: "numeric",
              })}
            </h2>
            <div className="row">
              <button
                className="btn"
                aria-label="Tháng trước"
                onClick={() => moveMonth(-1)}
              >
                Trước
              </button>
              <button
                className="btn"
                aria-label="Tháng sau"
                onClick={() => moveMonth(1)}
              >
                Sau
              </button>
            </div>
          </div>
          <div className="calendar-grid">
            {["T2", "T3", "T4", "T5", "T6", "T7", "CN"].map((day) => (
              <strong key={day}>{day}</strong>
            ))}
            {Array.from({ length: offset }, (_, index) => (
              <span key={`empty${index}`} />
            ))}
            {Array.from({ length: total }, (_, index) => {
              const day = index + 1;
              const date = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
              const count =
                data?.due_forecast.find((entry) => entry.date === date)
                  ?.count ?? 0;
              return (
                <button
                  key={date}
                  type="button"
                  className={`${selected === date ? "selected " : ""}${today === date ? "is-today " : ""}${count ? "has-due" : ""}`}
                  onClick={() => setSelected(date)}
                  aria-pressed={selected === date}
                  aria-current={today === date ? "date" : undefined}
                  aria-label={`Ngày ${label(date)}${today === date ? ", hôm nay" : ""}, ${count} thẻ đến hạn`}
                >
                  <span>{day}</span>
                  {count > 0 && <small>{count} thẻ</small>}
                </button>
              );
            })}
          </div>
          <div className="calendar-legend">
            <span>
              <i className="today-key" />
              Hôm nay
            </span>
            <span>
              <i className="selected-key" />
              Đang chọn
            </span>
            <span>
              <i className="due-key" />
              Có thẻ đến hạn
            </span>
          </div>
        </section>
        <aside
          className="panel stack"
          aria-label="Chi tiết ngày đã chọn"
          aria-live="polite"
        >
          <CalendarDays size={26} />
          <h2>Ngày {label(selected)}</h2>
          {data && (
            <>
              <p>
                {selectedDue > 0
                  ? `${selectedDue} thẻ đến hạn ôn trong ngày này.`
                  : "Không có thẻ đến hạn trong ngày này."}
              </p>
              {learned > 0 && <p>Đã học {learned} phút.</p>}
            </>
          )}
          {selected === today && selectedDue > 0 && (
            <Link className="btn primary" to="/luyen-tap/on-the">
              Ôn thẻ hôm nay
            </Link>
          )}
          <Link className="btn" to="/lo-trinh">
            Đề xuất lịch học
          </Link>
          <Link className="btn" to="/profile">
            Cài đặt ôn tập
          </Link>
          <div className="calendar-forecast">
            {data?.due_forecast.map((day) => (
              <button
                type="button"
                key={day.date}
                className="calendar-forecast-day"
                onClick={() => {
                  setSelected(day.date);
                  const date = new Date(`${day.date}T12:00:00`);
                  setMonth(new Date(date.getFullYear(), date.getMonth(), 1));
                }}
              >
                <span>{label(day.date)}</span>
                <strong>{day.count} thẻ</strong>
              </button>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
