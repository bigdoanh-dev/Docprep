import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { LearningActions } from "../../components/LearningActions";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import blueprint from "../../lib/blueprint.json";
import { useActor } from "../../app/identity";
import { Sheet } from "../../components/Sheet";
import { LoadError, Loading } from "../../components/Status";
import {
  api,
  type Listed,
  type Module,
  type ModuleDetail,
} from "../../lib/api";
import { useLoad } from "../../lib/hooks";

export function Modules() {
  const actor = useActor()!;
  const [params] = useSearchParams();
  const [advanced, setAdvanced] = useState({
    status: "",
    group: "",
    core_issue: "",
    level: "",
  });
  const [query, setQuery] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const appliedFilters = [...new URLSearchParams(query).keys()].filter(
    (k) => k !== "q",
  ).length;
  const { data, error, reload } = useLoad(
    () => api.get<Listed<Module>>(`/modules?${query}`),
    [query],
  );
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all"),
    [selectedId, setSelectedId] = useState<string | null>(params.get("hp"));
  const selected = data?.items.find((m) => m.id === selectedId) ?? null;
  const fold = (s: string) =>
    s
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/đ/g, "d");
  const items =
    data?.items.filter(
      (m) =>
        fold(m.name + " " + m.short_name).includes(fold(search)) &&
        (filter === "all" ||
          (filter === "available" && !m.coming_soon) ||
          (filter === "started" && m.units_done > 0)),
    ) ?? [];
  return (
    <div className="modules-page">
      <div className="page-heading">
        <h1>Học tập</h1>
        <p>Chọn nội dung theo khung năng lực Y học dự phòng.</p>
      </div>
      <LearningActions />
      <nav className="learning-secondary" aria-label="Kế hoạch học">
        <Link to="/lich-on">Lịch ôn</Link>
        <Link to="/lo-trinh">Lộ trình</Link>
        <Link to="/chon-hoc-phan?doi=1">Đổi trọng tâm</Link>
      </nav>
      <div className="module-toolbar">
        <div className="module-search-row">
          <label className="search-field">
            <Search size={19} />
            <input
              aria-label="Tìm học phần"
              placeholder="Tìm theo tên học phần…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <button
            className="module-filter-button"
            type="button"
            aria-label="Lọc chi tiết"
            aria-haspopup="dialog"
            onClick={() => setFiltersOpen(true)}
          >
            <SlidersHorizontal size={17} aria-hidden="true" /> Lọc
            {appliedFilters > 0 ? ` (${appliedFilters})` : ""}
          </button>
        </div>
        <div className="segmented">
          <button
            className={filter === "all" ? "active" : ""}
            onClick={() => setFilter("all")}
          >
            Tất cả
          </button>
          <button
            className={filter === "available" ? "active" : ""}
            onClick={() => setFilter("available")}
          >
            Có học liệu
          </button>
          <button
            className={filter === "started" ? "active" : ""}
            onClick={() => setFilter("started")}
          >
            Đã học
          </button>
        </div>
      </div>
      <Sheet
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Lọc học phần"
      >
        <div className="stack">
          <label className="field">
            Trạng thái
            <select
              value={advanced.status}
              onChange={(e) =>
                setAdvanced({ ...advanced, status: e.target.value })
              }
            >
              <option value="">Tất cả</option>
              <option value="not_started">Chưa bắt đầu</option>
              <option value="in_progress">Đang học</option>
              <option value="done">Hoàn thành</option>
            </select>
          </label>
          <label className="field">
            Nhóm năng lực
            <select
              value={advanced.group}
              onChange={(e) =>
                setAdvanced({ ...advanced, group: e.target.value })
              }
            >
              <option value="">Tất cả nhóm</option>
              {blueprint.groups.map((g) => (
                <option value={g.id} key={g.id}>
                  {g.short_name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Vấn đề cốt lõi
            <select
              value={advanced.core_issue}
              onChange={(e) =>
                setAdvanced({ ...advanced, core_issue: e.target.value })
              }
            >
              <option value="">Tất cả vấn đề</option>
              {blueprint.groups
                .flatMap((g) => g.issues)
                .map((i) => (
                  <option value={i.id} key={i.id}>
                    {i.id}. {i.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            Nhóm nhận thức
            <select
              value={advanced.level}
              onChange={(e) =>
                setAdvanced({ ...advanced, level: e.target.value })
              }
            >
              <option value="">Tất cả</option>
              <option value="1">Nhóm 1 · Nhớ và hiểu</option>
              <option value="2">Nhóm 2 · Vận dụng</option>
              <option value="3">Nhóm 3 · Phân tích và đánh giá</option>
            </select>
          </label>
          {actor.mode === "demo" && (
            <p className="notice">
              Câu nền tảng minh họa chưa gắn đủ mã 54 vấn đề. Bộ lọc chi tiết
              chỉ trả học liệu có metadata phù hợp.
            </p>
          )}
          <button
            className="btn primary"
            onClick={() => {
              setQuery(
                new URLSearchParams(
                  Object.entries({ ...advanced, q: search }).filter(
                    ([, v]) => v,
                  ),
                ).toString(),
              );
              setFiltersOpen(false);
            }}
          >
            Áp dụng bộ lọc
          </button>
          <button
            className="btn"
            onClick={() => {
              setQuery("");
              setSearch("");
              setFilter("all");
              setFiltersOpen(false);
              setAdvanced({ status: "", group: "", core_issue: "", level: "" });
            }}
          >
            Xóa bộ lọc
          </button>
        </div>
      </Sheet>
      {error && <LoadError message={error} onRetry={reload} />}{" "}
      {!data && !error && <Loading />}
      <div className="module-list-heading">
        <h2>Học phần</h2>
        <span>{items.length} học phần</span>
      </div>
      <div className="compact-modules">
        {items.map((m) => {
          const pct = m.units_total
            ? Math.round((m.units_done / m.units_total) * 100)
            : null;
          return (
            <button
              key={m.id}
              type="button"
              className="compact-module"
              aria-label={`${m.coming_soon ? "Xem phạm vi đề cương" : "Mở học phần"}: ${m.short_name}`}
              onClick={() => setSelectedId(m.id)}
            >
              <div className="compact-module-content">
                <h3>{m.short_name}</h3>
                <p>
                  {m.coming_soon
                    ? "Chưa có học liệu"
                    : `${m.units_done}/${m.units_total} bài đã học`}
                  <span> · {m.topics_total} vấn đề cốt lõi</span>
                </p>
                {pct !== null && (
                  <div className="compact-module-progress">
                    <div
                      className="progress"
                      role="progressbar"
                      aria-label={`Tiến độ ${m.short_name}`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={pct}
                    >
                      <span style={{ width: `${pct}%` }} />
                    </div>
                    <small>{pct}%</small>
                  </div>
                )}
                {m.coming_soon && (
                  <small className="module-outline-link">Xem đề cương</small>
                )}
              </div>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          );
        })}
      </div>
      {data && !items.length && (
        <p className="empty">
          Không có học phần phù hợp bộ lọc. Hãy đổi từ khóa.
        </p>
      )}
      <Sheet
        open={!!selected}
        onClose={() => setSelectedId(null)}
        title={selected?.short_name ?? "Học phần"}
      >
        {selected && (
          <ModuleContent id={selected.id} close={() => setSelectedId(null)} />
        )}
      </Sheet>
    </div>
  );
}
function ModuleContent({ id, close }: { id: string; close: () => void }) {
  const { data, error, reload } = useLoad(
    () => api.get<ModuleDetail>(`/modules/${id}`),
    [id],
  );
  if (error) return <LoadError message={error} onRetry={reload} />;
  if (!data) return <Loading />;
  return (
    <div className="module-detail-content">
      <p className="module-detail-description">{data.name}</p>
      {!data.units.length && (
        <p className="notice">
          Chưa có học liệu cho nhóm này trong kho hiện tại. Không tạo bài luyện
          hoặc số tiến độ giả.
        </p>
      )}
      {!!data.units.length && (
        <section className="module-detail-lessons">
          <div className="module-detail-lessons-heading">
            <h3>Chủ đề học</h3>
            <span>{data.units.length} bài</span>
          </div>
          <div className="module-detail-unit-list">
            {data.units.map((u) => (
              <Link
                key={u.id}
                className="module-unit-card"
                to={`/luyen-tap/${u.id}`}
                onClick={close}
              >
                <span className="module-unit-icon" aria-hidden="true">
                  <BookOpen size={18} />
                </span>
                <span className="module-unit-copy">
                  <strong>{u.topic}</strong>
                  <small className={u.done ? "is-complete" : ""}>
                    {u.done
                      ? "Đã hoàn thành"
                      : "Nội dung và câu hỏi tương tác"}
                  </small>
                </span>
                <span className="module-unit-indicator" aria-hidden="true">
                  {u.done ? (
                    <CheckCircle2 size={19} />
                  ) : (
                    <ArrowRight size={19} />
                  )}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
