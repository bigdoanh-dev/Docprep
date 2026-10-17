import { useState } from "react";
import { useActor } from "../../app/identity";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { useFeedback } from "../../components/ui/Feedback";
import { demoTransaction } from "../../lib/demo/store";
export function StudyPlan() {
  const actor = useActor()!,
    notify = useFeedback();
  const [minutes, setMinutes] = useState(30),
    [time, setTime] = useState("20:00"),
    [days, setDays] = useState<string[]>(["T2", "T3", "T4", "T5", "T6"]),
    [proposal, setProposal] = useState<any>(null);
  return (
    <div>
      <header className="page-heading">
        <h1>Đề xuất lịch học</h1>
        <p>Phân bổ thời gian theo quỹ giờ bạn có thể dành cho việc ôn tập.</p>
      </header>
      <FutureNotice name="Lộ trình dài hạn" />
      <div className="settings-grid">
        <form
          className="panel stack"
          onSubmit={(e) => {
            e.preventDefault();
            setProposal({
              minutes,
              time,
              days,
              cards: Math.min(10, Math.floor(minutes / 3)),
              practice: Math.floor(minutes * 0.5),
              continue:
                minutes -
                Math.min(10, Math.floor(minutes / 3)) -
                Math.floor(minutes * 0.5),
            });
          }}
        >
          <label className="field">
            Phút học mỗi buổi
            <input
              type="number"
              min={15}
              max={180}
              value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}
            />
          </label>
          <label className="field">
            Giờ bắt đầu
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
            />
          </label>
          <div className="day-picker">
            {["T2", "T3", "T4", "T5", "T6", "T7", "CN"].map((d) => (
              <button
                type="button"
                key={d}
                aria-pressed={days.includes(d)}
                className={days.includes(d) ? "active" : ""}
                onClick={() =>
                  setDays(
                    days.includes(d)
                      ? days.filter((v) => v !== d)
                      : [...days, d],
                  )
                }
              >
                {d}
              </button>
            ))}
          </div>
          <button
            className="btn primary"
            disabled={actor.mode !== "demo" || !days.length}
          >
            Xem đề xuất minh họa
          </button>
        </form>
        <section className="panel stack">
          {proposal ? (
            <>
              <h2>
                {proposal.time}, {proposal.minutes} phút mỗi buổi
              </h2>
              <p>{proposal.days.join(", ")}</p>
              <ol className="workflow-list">
                <li>Ôn thẻ: {proposal.cards} phút</li>
                <li>Luyện điểm yếu: {proposal.practice} phút</li>
                <li>Học tiếp: {proposal.continue} phút</li>
              </ol>
              <p className="notice">
                Chỉ là phân bổ thời gian minh họa; chưa tính đủ tiên quyết và
                khoảng cách năng lực như bộ máy R2.
              </p>
              <button
                className="btn primary"
                onClick={() => {
                  demoTransaction((s) => {
                    s.studyPlan = proposal;
                    return proposal;
                  });
                  notify("Đã lưu kế hoạch minh họa trên trình duyệt.");
                }}
              >
                Áp dụng kế hoạch minh họa
              </button>
            </>
          ) : (
            <p className="empty">
              Nhập quỹ thời gian để xem đề xuất. Không có thay đổi nào được áp
              dụng tự động.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
