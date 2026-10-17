import { ArrowRight, Flag } from "lucide-react";
import { useState } from "react";
import { useActor } from "../../app/identity";
import { Sheet } from "../../components/Sheet";
import { LoadError } from "../../components/Status";
import { useFeedback } from "../../components/ui/Feedback";
import { api } from "../../lib/api";
import { demoTransaction } from "../../lib/demo/store";
import { useLoad } from "../../lib/hooks";
export function Reports() {
  const actor = useActor()!,
    notify = useFeedback(),
    { data, error, reload } = useLoad(
      () => api.get<any>("/review/reports?limit=100"),
      [],
    );
  const [selected, setSelected] = useState<any>(null);
  return (
    <div>
      <header className="page-heading">
        <h1>Báo lỗi từ người học</h1>
        <p>Xem ngữ cảnh, rà soát nội dung và phản hồi xử lý.</p>
      </header>
      {error && <LoadError message={error} onRetry={reload} />}
      <div className="card-library">
        {data?.items.map((r: any) => (
          <button key={r.id} onClick={() => setSelected(r)}>
            <Flag size={20} />
            <span>
              <strong>
                {r.target_id} · {r.reason}
              </strong>
              <small>
                {r.note} · {r.status === "open" ? "Đang xử lý" : "Đã xử lý"}
              </small>
            </span>
            <ArrowRight size={17} />
          </button>
        ))}
      </div>
      {data && !data.items.length && (
        <p className="empty">
          Chưa có báo lỗi. Báo lỗi gửi từ màn câu hỏi hoặc hội thoại sẽ xuất
          hiện ở đây.
        </p>
      )}
      <Sheet
        open={!!selected}
        onClose={() => setSelected(null)}
        title="Chi tiết báo lỗi"
      >
        {selected && (
          <div className="stack">
            <p>
              <strong>{selected.target_id}</strong>
            </p>
            <p>{selected.note}</p>
            <pre>{JSON.stringify(selected.context, null, 2)}</pre>
            <p>Trạng thái: {selected.status}</p>
            <button
              className="btn primary"
              disabled={actor.mode !== "demo" || selected.status === "resolved"}
              onClick={() => {
                demoTransaction((s) => {
                  s.reports.find((r: any) => r.id === selected.id).status =
                    "resolved";
                  return null;
                });
                notify("Đã ghi nhận xử lý báo lỗi minh họa.");
                setSelected(null);
                reload();
              }}
            >
              Đánh dấu đã xử lý minh họa
            </button>
            {actor.mode === "live" && (
              <p className="notice">
                Chưa có thao tác cập nhật trạng thái báo lỗi trên máy chủ hiện
                tại.
              </p>
            )}
          </div>
        )}
      </Sheet>
    </div>
  );
}
