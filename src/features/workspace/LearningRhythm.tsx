import { Flame, CheckCircle2 } from "lucide-react";
import { localDay, streak, useWorkspace } from "../../lib/learnerWorkspace";
export function LearningRhythm() {
  const w = useWorkspace(),
    days = w.activity.map((a) => a.date),
    today = localDay();
  const n = streak(days, today);
  const week = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(`${today}T12:00:00+07:00`);
    d.setDate(d.getDate() - 6 + i);
    return {
      id: localDay(d),
      label: new Intl.DateTimeFormat("vi", {
        weekday: "short",
        timeZone: "Asia/Ho_Chi_Minh",
      })
        .format(d)
        .replace("Thứ ", "T"),
    };
  });
  return (
    <section className="learning-rhythm">
      <div className="learning-rhythm-info">
        <span className="learning-rhythm-badge" aria-hidden="true">
          <Flame size={20} />
        </span>
        <div>
          <strong>{n} ngày ôn liên tiếp</strong>
          <small>
            {days.includes(today)
              ? "Bạn đã học hôm nay. Tiếp tục giữ nhịp nhé."
              : "Hoàn thành một câu hoặc ôn một thẻ để giữ nhịp."}
          </small>
        </div>
      </div>
      <div className="week-days">
        {week.map((d) => (
          <span key={d.id} className={days.includes(d.id) ? "learned" : ""}>
            <small>{d.label}</small>
            {days.includes(d.id) ? (
              <CheckCircle2 size={16} />
            ) : (
              <span className="week-day-idle" aria-label="Chưa ghi nhận học" />
            )}
          </span>
        ))}
      </div>
    </section>
  );
}
