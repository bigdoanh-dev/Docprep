import { ArrowRight, BookOpen, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useActor } from "../../app/identity";
import { SourceSheet } from "../../components/Answer";
import { Sheet } from "../../components/Sheet";
import { LoadError } from "../../components/Status";
import { useFeedback } from "../../components/ui/Feedback";
import { api, type DueCardList } from "../../lib/api";
import { readStore } from "../../lib/demo/store";
import { useLoad } from "../../lib/hooks";
export function CardBrowser() {
  const actor = useActor()!,
    notify = useFeedback();
  const { data, error, reload } = useLoad(
    async () =>
      actor.mode === "demo"
        ? { items: readStore().cards, total_due: 0 }
        : api.get<DueCardList>("/cards/due"),
    [actor.mode],
  );
  const [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [selected, setSelected] = useState<any>(null),
    [source, setSource] = useState<any>(null);
  const items = (data?.items ?? []).filter(
    (c: any) =>
      c.front.toLowerCase().includes(query.toLowerCase()) &&
      (filter === "all" ||
        (filter === "hidden" && c.suspended) ||
        (filter === "due" &&
          !c.suspended &&
          Date.parse(c.due_at ?? new Date().toISOString()) <= Date.now())),
  );
  return (
    <div>
      <header className="page-heading">
        <h1>Thư viện thẻ ôn</h1>
        <p>Xem nguồn, tìm thẻ và quản lý những thẻ tạm ẩn.</p>
      </header>
      {actor.mode === "live" && (
        <p className="notice">
          Máy chủ hiện chỉ cung cấp danh sách thẻ đến hạn, chưa cung cấp toàn bộ
          thư viện thẻ.
        </p>
      )}
      <div className="module-toolbar">
        <label className="search-field">
          <Search size={18} />
          <input
            aria-label="Tìm thẻ"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm nội dung thẻ…"
          />
        </label>
        <select
          aria-label="Lọc thẻ"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">Tất cả thẻ được tải</option>
          <option value="due">Đến hạn</option>
          <option value="hidden">Tạm ẩn</option>
        </select>
        <Link className="btn" to="/profile">
          Cài đặt ôn
        </Link>
      </div>
      {error && <LoadError message={error} onRetry={reload} />}
      <div className="card-library">
        {items.map((c: any) => (
          <button key={c.id} onClick={() => setSelected(c)}>
            <BookOpen size={20} />
            <span>
              <strong>{c.front}</strong>
              <small>
                {c.module} · {c.suspended ? "Tạm ẩn" : "Đang ôn"}
              </small>
            </span>
            <ArrowRight size={17} />
          </button>
        ))}
      </div>
      {data && !items.length && <p className="empty">Không có thẻ phù hợp.</p>}
      <Sheet
        open={!!selected}
        onClose={() => setSelected(null)}
        title="Chi tiết thẻ"
      >
        {selected && (
          <div className="stack">
            <h3>{selected.front}</h3>
            <p className="reading">{selected.back}</p>
            <button
              className="btn"
              onClick={() =>
                setSource({
                  n: 1,
                  passage_id: selected.source_passage_id,
                  document: selected.citation,
                  page: null,
                  chapter: null,
                  section: null,
                  article: null,
                })
              }
            >
              Mở nguồn
            </button>
            <button
              className="btn"
              onClick={async () => {
                try {
                  await api.patch(`/cards/${selected.id}`, {
                    suspended: !selected.suspended,
                  });
                  notify(
                    selected.suspended ? "Đã mở lại thẻ." : "Đã tạm ẩn thẻ.",
                  );
                  setSelected(null);
                  reload();
                } catch (e) {
                  notify((e as Error).message, "error");
                }
              }}
            >
              {selected.suspended ? "Mở lại thẻ" : "Tạm ẩn thẻ"}
            </button>
          </div>
        )}
      </Sheet>
      <SourceSheet citation={source} onClose={() => setSource(null)} />
    </div>
  );
}
