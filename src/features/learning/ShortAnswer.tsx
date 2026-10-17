import { useState } from "react";
import { useActor } from "../../app/identity";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { useFeedback } from "../../components/ui/Feedback";
export function ShortAnswer() {
  const actor = useActor()!,
    [answer, setAnswer] = useState(""),
    [submitted, setSubmitted] = useState(false),
    [checks, setChecks] = useState<boolean[]>([false, false]),
    notify = useFeedback();
  return (
    <div className="screen">
      <header className="page-heading">
        <h1>Luyện câu trả lời ngắn</h1>
        <p>Đối chiếu câu trả lời theo từng ý của rubric.</p>
      </header>
      <FutureNotice name="Chấm trả lời ngắn" />
      <section className="panel stack">
        <h2>Vì sao hiện mắc có thể tăng khi mới mắc không đổi?</h2>
        <label className="field">
          Câu trả lời của bạn
          <textarea
            rows={5}
            value={answer}
            onChange={(e) => {
              setAnswer(e.target.value);
              setSubmitted(false);
            }}
            placeholder="Giải thích bằng các ý ngắn…"
          />
        </label>
        <button
          className="btn primary"
          disabled={actor.mode !== "demo" || !answer.trim()}
          onClick={() => setSubmitted(true)}
        >
          Đối chiếu rubric minh họa
        </button>
        {submitted && (
          <div className="feedback-panel uncertain">
            <h3>Chưa có kết quả chấm tự động</h3>
            <p>
              Bản minh họa không gọi mô hình và không cộng điểm năng lực. Bạn tự
              đối chiếu với hai ý sau.
            </p>
            {[
              "Hiện mắc phụ thuộc thời gian mắc bệnh.",
              "Thời gian mắc bệnh dài hơn làm số người đang mắc tích lũy, khi mới mắc không đổi.",
            ].map((s, i) => (
              <label key={s} className="check">
                <input
                  type="checkbox"
                  checked={checks[i]}
                  onChange={(e) =>
                    setChecks(
                      checks.map((v, j) => (i === j ? e.target.checked : v)),
                    )
                  }
                />
                {s}
              </label>
            ))}
            <p>Đáp án mẫu: P ≈ I × D. I không đổi, D tăng thì P tăng.</p>
            <button
              className="btn"
              onClick={() =>
                notify(
                  "Đã ghi nhận tự đối chiếu trong phiên này; không cập nhật mức thành thạo.",
                  "info",
                )
              }
            >
              Ghi nhận tự đối chiếu
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
