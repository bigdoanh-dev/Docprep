import { BookOpen } from "lucide-react";
import { useState } from "react";
import { useActor } from "../../app/identity";
import { SourceSheet } from "../../components/Answer";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { citations } from "../../lib/demo/store";
export function ConceptMap() {
  const actor = useActor()!,
    [source, setSource] = useState<any>(null);
  return (
    <div>
      <header className="page-heading">
        <h1>Sơ đồ khái niệm</h1>
        <p>Liên hệ giữa hiện mắc, mới mắc và thời gian mắc bệnh.</p>
      </header>
      <FutureNotice name="Sơ đồ khái niệm" />
      <div className="concept-map">
        {["Tỷ lệ hiện mắc", "Tỷ lệ mới mắc", "Thời gian mắc bệnh"].map(
          (label, i) => (
            <button
              key={label}
              disabled={actor.mode !== "demo"}
              onClick={() =>
                setSource(citations([["dt-p01", "dt-p02", "dt-p03"][i]])[0])
              }
            >
              <BookOpen size={25} />
              <strong>{label}</strong>
              <small>Mở đoạn học liệu minh họa</small>
            </button>
          ),
        )}
      </div>
      <p className="notice">
        Quan hệ minh họa: P ≈ I × D. Sơ đồ này dùng dữ liệu minh họa, chưa được tổng hợp từ
        kho thật.
      </p>
      <SourceSheet citation={source} onClose={() => setSource(null)} />
    </div>
  );
}
