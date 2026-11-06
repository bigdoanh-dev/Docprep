import { useState } from "react";
import { useActor } from "../../app/identity";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { useFeedback } from "../../components/ui/Feedback";
import { demoTransaction, readStore } from "../../lib/demo/store";
export function StudyPlan() {
  const actor = useActor()!,
    notify = useFeedback();
  const [saved] = useState(() =>
    actor.mode === "demo" ? readStore().studyPlan : null,
  );
  const [minutes, setMinutes] = useState(saved?.minutes ?? 30),
    [time, setTime] = useState(saved?.time ?? "20:00"),
    [days, setDays] = useState<string[]>(
      saved?.days ?? ["T2", "T3", "T4", "T5", "T6"],
    ),
    [proposal, setProposal] = useState<any>(saved);
  return (
    <div>
      <header className="page-heading">
        <h1>Đề xuất lịch học</h1>
        <p>Phân bổ thời gian theo quỹ giờ bạn có thể dành cho việc ôn tập.</p>
      </header>
      {actor.mode !== "demo" && <FutureNotice name="Lộ trình dài hạn" />}
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
              required
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
              required
              value={time}
              onChange={(e) => setTime(e.target.value)}
            />
          </label>
          <p className="label">Ngày học trong tuần</p>
          <div
            className="day-picker"
            role="group"
            aria-label="Ngày học trong tuần"
          >
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
            disabled={
              actor.mode !== "demo" ||
              !days.length ||
              !Number.isInteger(minutes) ||
              minutes < 15 ||
              minutes > 180 ||
              !time
            }
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
                Kế hoạch minh họa được lưu trên thiết bị này. Bạn có thể điều
                chỉnh thời lượng và ngày học.
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
            <div className="empty">
              <h2>Lịch học của bạn</h2>
              <p>
                Chọn thời lượng, giờ bắt đầu và ngày học, sau đó nhấn “Xem đề
                xuất minh họa”.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
