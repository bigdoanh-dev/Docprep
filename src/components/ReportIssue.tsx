import { Flag } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useActor } from "../app/identity";
import { api, ApiError } from "../lib/api";
import { updateWorkspace } from "../lib/learnerWorkspace";
import { Sheet } from "./Sheet";
const reasons = [
  ["wrong_content", "Nội dung chưa đúng"],
  ["wrong_citation", "Nguồn trích dẫn chưa phù hợp"],
  ["broken_item", "Lỗi hiển thị hoặc phương án"],
  ["inappropriate", "Nội dung không phù hợp"],
  ["other", "Lý do khác"],
];
export function ReportIssue({
  id,
  title,
  target = "question",
}: {
  id: string;
  title: string;
  target?: "question" | "answer" | "card" | "content";
}) {
  const actor = useActor()!;
  const [open, setOpen] = useState(false),
    [reason, setReason] = useState("wrong_content"),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [status, setStatus] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const body = {
        target_type: target,
        target_id: id,
        reason,
        note: note.trim() || null,
        context: { screen: location.pathname },
      };
      if (actor.mode === "demo") {
        updateWorkspace((w) => ({
          ...w,
          reportDrafts: [
            ...(w.reportDrafts ?? []),
            { ...body, created_at: new Date().toISOString() },
          ],
        }));
        setStatus(
          "Đã lưu phản ánh mẫu trên trình duyệt. Chưa gửi đến bộ phận xử lý.",
        );
      } else {
        const result = await api.post<{ id: number }>("/reports", body);
        setStatus(`Đã tiếp nhận phản ánh số ${result.id}.`);
      }
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 501
          ? "Máy chủ chưa hỗ trợ tiếp nhận phản ánh. Nội dung bạn nhập vẫn được giữ để thử lại."
          : (e as Error).message,
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <button
        type="button"
        className="report-issue"
        onClick={() => {
          setOpen(true);
          setStatus("");
        }}
      >
        <Flag size={13} />
        Báo lỗi nội dung
      </button>
      <Sheet
        open={open}
        onClose={() => !busy && setOpen(false)}
        title="Báo lỗi nội dung"
      >
        <form className="stack" onSubmit={submit}>
          <p className="small">{title}</p>
          <label className="field">
            Lý do
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              {reasons.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Mô tả thêm
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={2000}
              rows={4}
              placeholder="Mô tả vấn đề, không nhập thông tin người bệnh"
            />
          </label>
          {actor.mode === "demo" && (
            <p className="notice">
              Phản ánh mẫu chỉ lưu tại thiết bị này, không tạo hàng đợi xử lý
              của cán bộ.
            </p>
          )}
          {error && (
            <p className="warn" role="alert">
              {error}
            </p>
          )}
          {status ? (
            <p role="status" className="notice">
              {status}
            </p>
          ) : (
            <button className="btn primary" disabled={busy}>
              {busy
                ? "Đang xử lý…"
                : actor.mode === "demo"
                  ? "Lưu phản ánh mẫu"
                  : "Gửi phản ánh"}
            </button>
          )}
        </form>
      </Sheet>
    </>
  );
}
