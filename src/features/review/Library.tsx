import { ArrowRight, BookOpen, Search } from "lucide-react";
import { useState } from "react";
import { useActor } from "../../app/identity";
import { Sheet } from "../../components/Sheet";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { passages } from "../../lib/demo/store";
export function Library() {
  const actor = useActor()!,
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState<any>(null);
  return (
    <div>
      <header className="page-heading">
        <h1>Thư viện học liệu</h1>
        <p>Tra cứu nguồn, vị trí trang và phiên bản dùng để thẩm định.</p>
      </header>
      <FutureNotice release="api" name="Thư viện quản trị học liệu" />
      <label className="search-field">
        <Search size={18} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Tìm tài liệu hoặc đoạn…"
          aria-label="Tìm học liệu"
        />
      </label>
      {actor.mode === "demo" && (
        <div className="card-library">
          {passages
            .filter((p: any) =>
              (p.document + " " + p.section + " " + p.excerpt)
                .toLowerCase()
                .includes(query.toLowerCase()),
            )
            .map((p: any) => (
              <button key={p.id} onClick={() => setSelected(p)}>
                <BookOpen size={20} />
                <span>
                  <strong>{p.section ?? p.document}</strong>
                  <small>
                    {p.document} · trang {p.page} · {p.id}
                  </small>
                </span>
                <ArrowRight size={17} />
              </button>
            ))}
        </div>
      )}
      <Sheet
        open={!!selected}
        onClose={() => setSelected(null)}
        title="Đoạn học liệu"
      >
        {selected && (
          <div className="stack">
            <h3>{selected.document}</h3>
            <p>
              {selected.chapter} · trang {selected.page}
            </p>
            <p className="reading">{selected.excerpt}</p>
            <p className="notice">{selected.demo_label}</p>
          </div>
        )}
      </Sheet>
    </div>
  );
}
