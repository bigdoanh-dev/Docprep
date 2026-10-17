import { useState } from "react";
import { Bookmark, NotebookPen, Search, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import {
  updateWorkspace,
  useWorkspace,
  type SavedQuestion,
} from "../../lib/learnerWorkspace";
import { useFeedback } from "../../components/ui/Feedback";
export function Notebook() {
  const w = useWorkspace();
  const [search, setSearch] = useState(""),
    [tab, setTab] = useState("all");
  const rows = w.saved.filter(
    (q) =>
      (tab !== "notes" || q.note) &&
      `${q.title} ${q.note}`
        .toLocaleLowerCase("vi")
        .includes(search.toLocaleLowerCase("vi")),
  );
  return (
    <div className="screen stack">
      <header className="page-heading">
        <h1>Sổ tay của bạn</h1>
        <p>Câu hỏi đã lưu và ghi chú để ôn lại bất cứ lúc nào.</p>
      </header>
      <div className="module-toolbar">
        <label className="search-field">
          <Search size={19} />
          <input
            aria-label="Tìm trong sổ tay"
            placeholder="Tìm câu hỏi hoặc ghi chú…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <div className="segmented">
          <button
            className={tab === "all" ? "active" : ""}
            onClick={() => setTab("all")}
          >
            Đã lưu ({w.saved.length})
          </button>
          <button
            className={tab === "notes" ? "active" : ""}
            onClick={() => setTab("notes")}
          >
            Có ghi chú
          </button>
        </div>
      </div>
      <p className="muted small">
        Sổ tay được lưu trên trình duyệt này, theo tài khoản hiện tại.
      </p>
      {rows.length ? (
        rows.map((q) => <NoteItem key={q.id} question={q} />)
      ) : (
        <section className="empty">
          <Bookmark size={32} />
          <h2>
            {w.saved.length
              ? "Không tìm thấy câu hỏi phù hợp"
              : "Bắt đầu sổ tay của bạn"}
          </h2>
          <p>
            Bấm “Lưu câu hỏi” khi luyện tập hoặc ôn thẻ, rồi thêm ghi chú riêng.
          </p>
          <Link to="/on-tap" className="btn primary">
            Đi đến ôn tập
          </Link>
        </section>
      )}
    </div>
  );
}
function NoteItem({ question: q }: { question: SavedQuestion }) {
  const [note, setNote] = useState(q.note),
    [remove, setRemove] = useState(false),
    notify = useFeedback();
  return (
    <article className="panel stack">
      <div className="row">
        <NotebookPen size={22} />
        <h2 className="grow">{q.title}</h2>
        <button
          className="icon-btn"
          aria-label="Bỏ lưu câu hỏi"
          onClick={() => setRemove(true)}
        >
          <Trash2 size={18} />
        </button>
      </div>
      {q.detail && <p>{q.detail}</p>}
      {q.source && <p className="muted small">Nguồn: {q.source}</p>}
      <label className="field">
        Ghi chú của bạn
        <textarea
          rows={3}
          maxLength={5000}
          placeholder="Điểm cần nhớ, cách suy luận hoặc điều cần ôn lại…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
      <button
        className="btn primary"
        onClick={() => {
          updateWorkspace((w) => ({
            ...w,
            saved: w.saved.map((s) => (s.id === q.id ? { ...s, note } : s)),
          }));
          notify("Đã lưu ghi chú.");
        }}
      >
        Lưu ghi chú
      </button>
      {remove && (
        <div className="notice row">
          <p className="grow">Bỏ lưu sẽ xóa cả ghi chú của câu này.</p>
          <button className="btn" onClick={() => setRemove(false)}>
            Giữ lại
          </button>
          <button
            className="btn"
            onClick={() =>
              updateWorkspace((w) => ({
                ...w,
                saved: w.saved.filter((s) => s.id !== q.id),
              }))
            }
          >
            Bỏ lưu
          </button>
        </div>
      )}
    </article>
  );
}
