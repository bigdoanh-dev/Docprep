import { ArrowRight, FileCheck2, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useActor } from "../../app/identity";
import { LoadError, Loading } from "../../components/Status";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { api } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { statusName } from "./status";
export function Queue() {
  const actor = useActor()!,
    [search, setSearch] = useState(""),
    [round, setRound] = useState("all");
  const { data, error, reload } = useLoad(
    () => api.get<any>("/review/queue?limit=100"),
    [],
  );
  const items = (data?.items ?? []).filter(
    (r: any) =>
      r.title.toLowerCase().includes(search.toLowerCase()) &&
      (round === "all" || String(r.round) === round),
  );
  return (
    <div>
      <header className="page-heading">
        <h1>Hàng đợi thẩm định</h1>
        <p>
          Kiểm tra nội dung chuyên môn và kỹ thuật khảo thí qua hai vòng độc
          lập.
        </p>
      </header>
      {actor.mode === "live" && (
        <FutureNotice release="api" name="Bàn thẩm định" />
      )}
      <div className="module-toolbar">
        <label className="search-field">
          <Search size={18} />
          <input
            aria-label="Tìm câu thẩm định"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm câu hỏi…"
          />
        </label>
        <select
          aria-label="Vòng thẩm định"
          value={round}
          onChange={(e) => setRound(e.target.value)}
        >
          <option value="all">Cả hai vòng</option>
          <option value="1">Vòng 1 — chuyên môn</option>
          <option value="2">Vòng 2 — khảo thí</option>
        </select>
        <span className="muted">{items.length} mục phù hợp</span>
      </div>
      {error && <LoadError message={error} onRetry={reload} />}{" "}
      {!data && !error && <Loading />}
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Câu hỏi</th>
              <th>Phiên bản</th>
              <th>Vòng duyệt</th>
              <th>Trạng thái</th>
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r: any) => (
              <tr key={r.id}>
                <td>
                  <strong>{r.title}</strong>
                  <small>
                    {r.id} ·{" "}
                    {r.ai_assisted ? "Nháp có AI hỗ trợ" : "Nguồn biên soạn"}
                  </small>
                </td>
                <td>{r.version}</td>
                <td>{r.round === 1 ? "Chuyên môn" : "Khảo thí"}</td>
                <td>
                  <span className="status-tag">
                    {statusName[r.status] ?? r.status}
                  </span>
                </td>
                <td>
                  <Link className="btn" to={`/tham-dinh/cau/${r.id}`}>
                    Thẩm định
                    <ArrowRight size={15} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && !items.length && (
        <div className="empty">
          <FileCheck2 size={32} />
          <p>Không có câu cần duyệt theo bộ lọc này.</p>
        </div>
      )}
    </div>
  );
}
