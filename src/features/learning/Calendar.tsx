import { CalendarDays } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { LoadError } from "../../components/Status";
import { api, type ProgressRhythm } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
export function Calendar() {
  const { data, error, reload } = useLoad(
    () => api.get<ProgressRhythm>("/progress/rhythm"),
    [],
  );
  const [month, setMonth] = useState(new Date()),
    [selected, setSelected] = useState(new Date().getDate());
  const first = new Date(month.getFullYear(), month.getMonth(), 1),
    offset = (first.getDay() + 6) % 7,
    total = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  return (
    <div className="calendar-page">
      <header className="page-heading">
        <h1>Lịch ôn tập</h1>
        <p>Theo dõi nhịp học và những thẻ cần ôn lại.</p>
      </header>
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
                onClick={() =>
                  setMonth(
                    new Date(month.getFullYear(), month.getMonth() - 1, 1),
                  )
                }
              >
                Trước
              </button>
              <button
                className="btn"
                aria-label="Tháng sau"
                onClick={() =>
                  setMonth(
                    new Date(month.getFullYear(), month.getMonth() + 1, 1),
                  )
                }
              >
                Sau
              </button>
            </div>
          </div>
          <div className="calendar-grid">
            {["T2", "T3", "T4", "T5", "T6", "T7", "CN"].map((d) => (
              <strong key={d}>{d}</strong>
            ))}
            {Array.from({ length: offset }, (_, i) => (
              <span key={`empty${i}`} />
            ))}
            {Array.from({ length: total }, (_, i) => {
              const day = i + 1,
                date = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
                n = data?.due_forecast.find((d) => d.date === date)?.count ?? 0;
              return (
                <button
                  key={day}
                  className={selected === day ? "selected" : ""}
                  onClick={() => setSelected(day)}
                  aria-label={`Ngày ${day}, ${n} thẻ đến hạn`}
                >
                  <span>{day}</span>
                  {n > 0 && <small>{n} thẻ</small>}
                </button>
              );
            })}
          </div>
          <p className="muted small">
            Chỉ đánh dấu các ngày có dữ liệu lịch ôn. Không tự tạo ngày học.
          </p>
        </section>
        <aside className="panel stack">
          <CalendarDays size={30} />
          <h2>
            Ngày {selected}/{month.getMonth() + 1}
          </h2>
          <p>
            Ôn thẻ theo danh sách đến hạn hiện tại. Ngày đã chọn dùng để xem
            lịch.
          </p>
          <Link className="btn primary" to="/luyen-tap/on-the">
            Ôn thẻ đến hạn
          </Link>
          <Link className="btn" to="/lo-trinh">
            Đề xuất lịch học
          </Link>
          <Link className="btn" to="/profile">
            Cài đặt ôn tập
          </Link>
          {error && <LoadError message={error} onRetry={reload} />}
          <div className="calendar-forecast">
            {data?.due_forecast.map((d) => (
              <p key={d.date}>
                <span>{new Date(d.date).toLocaleDateString("vi-VN")}</span>
                <strong>{d.count} thẻ</strong>
              </p>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
