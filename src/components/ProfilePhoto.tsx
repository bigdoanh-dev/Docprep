import { Camera, ImagePlus, Trash2 } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";
import { Sheet } from "./Sheet";
import { updateWorkspace, useWorkspace } from "../lib/learnerWorkspace";
export function ProfilePhoto() {
  const w = useWorkspace();
  const [open, setOpen] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const upload = useRef<HTMLInputElement>(null),
    camera = useRef<HTMLInputElement>(null);
  async function choose(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError("");
    setBusy(true);
    try {
      if (!file.type.startsWith("image/") || file.size > 10 * 1024 * 1024)
        throw new Error("Chọn ảnh dưới 10 MB.");
      const bitmap = await createImageBitmap(file);
      const canvas = document.createElement("canvas"),
        ratio = Math.min(1, 512 / Math.max(bitmap.width, bitmap.height));
      canvas.width = Math.max(1, Math.round(bitmap.width * ratio));
      canvas.height = Math.max(1, Math.round(bitmap.height * ratio));
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Không thể xử lý ảnh. Hãy thử ảnh khác.");
      ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();
      updateWorkspace((prev) => ({
        ...prev,
        avatarUrl: canvas.toDataURL("image/jpeg", 0.85),
      }));
      setOpen(false);
    } catch {
      setError(
        "Không lưu được ảnh. Chọn ảnh JPG/PNG dưới 10 MB và kiểm tra dung lượng trình duyệt.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        className="btn"
        onClick={() => {
          setError("");
          setOpen(true);
        }}
      >
        <Camera size={18} />
        Chỉnh sửa ảnh
      </button>
      <p className="muted small">
        Ảnh lưu trên thiết bị này theo tài khoản của bạn.
      </p>
      <input
        ref={upload}
        type="file"
        accept="image/*"
        hidden
        onChange={choose}
      />
      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="user"
        hidden
        onChange={choose}
      />
      <Sheet
        open={open}
        onClose={() => !busy && setOpen(false)}
        title="Ảnh đại diện"
      >
        <div className="stack">
          <button
            className="btn"
            disabled={busy}
            onClick={() => upload.current?.click()}
          >
            <ImagePlus size={18} />
            Tải ảnh lên
          </button>
          <button
            className="btn"
            disabled={busy}
            onClick={() => camera.current?.click()}
          >
            <Camera size={18} />
            Chụp ảnh
          </button>
          <p className="muted small">
            Chụp ảnh mở camera trên thiết bị hỗ trợ; máy tính có thể mở bộ chọn
            tệp.
          </p>
          {w.avatarUrl && (
            <button
              className="btn"
              disabled={busy}
              onClick={() => {
                updateWorkspace((prev) => ({ ...prev, avatarUrl: null }));
                setOpen(false);
              }}
            >
              <Trash2 size={18} />
              Xóa ảnh
            </button>
          )}
          {busy && <p role="status">Đang lưu ảnh…</p>}
          {error && <p role="alert">{error}</p>}
        </div>
      </Sheet>
    </>
  );
}
