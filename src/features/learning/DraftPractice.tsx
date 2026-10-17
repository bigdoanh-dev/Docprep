import { useState } from "react";
import { useActor } from "../../app/identity";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { seed } from "../../lib/demo/store";
export function DraftPractice() {
  const actor = useActor()!,
    [chosen, setChosen] = useState(""),
    [checked, setChecked] = useState(false),
    q = seed.questions[1];
  return (
    <div className="screen">
      <header className="page-heading">
        <h1>Câu hỏi có AI hỗ trợ</h1>
        <p>Luồng luyện tự chọn thuộc phạm vi cần chốt ở R2.</p>
      </header>
      <FutureNotice name="Câu hỏi hạng B" />
      <p className="warn">
        Chưa qua thẩm định chuyên gia. Không dùng thi thử, chẩn đoán hoặc cập
        nhật năng lực.
      </p>
      <section className="panel stack">
        <h2>{q.stem}</h2>
        {q.options.map((o: any) => (
          <button
            className={`btn option ${chosen === o.key ? "picked" : ""}`}
            key={o.key}
            disabled={actor.mode !== "demo" || checked}
            onClick={() => setChosen(o.key)}
          >
            {o.key.toUpperCase()}. {o.text}
          </button>
        ))}
        <button
          className="btn primary"
          disabled={!chosen || checked}
          onClick={() => setChecked(true)}
        >
          Kiểm tra minh họa
        </button>
        {checked && (
          <div className="notice">
            <p>{q.explanation}</p>
            <strong>
              Kết quả này không cập nhật hồ sơ năng lực hoặc tạo thẻ ôn.
            </strong>
          </div>
        )}
      </section>
    </div>
  );
}
