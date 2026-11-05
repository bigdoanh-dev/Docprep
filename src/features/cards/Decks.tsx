import { Link } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { LoadError, Loading } from "../../components/Status";
import { TabBar } from "../../components/TabBar";
import { api, type Deck, type Listed } from "../../lib/api";
import { useLoad } from "../../lib/hooks";

// Bộ thẻ (FR-LRN-34): one deck per học phần with its new, learning and due cards. R1.0 simple: no
// leech deck, no deck detail, no browser.
export function Decks() {
  const { data, error, reload } = useLoad(
    () => api.get<Listed<Deck>>("/decks"),
    [],
  );
  const decks = data?.items ?? [];
  const sum = (count: (d: Deck) => number) =>
    decks.reduce((total, d) => total + count(d), 0);
  const due = sum((d) => d.due);

  return (
    <div className="screen">
      <header className="topbar">
        <Link to="/" className="icon-btn" aria-label="Về trang chủ">
          <Icon name="left" />
        </Link>
        <h1>Bộ thẻ</h1>
      </header>
      <div className="body stack">
        <div className="row">
          <Link className="btn" to="/luyen-tap/duyet-the">
            Duyệt thư viện thẻ
          </Link>
          <Link className="btn" to="/profile">
            Cài đặt ôn
          </Link>
        </div>
        {error && <LoadError message={error} onRetry={reload} />}
        {!data && !error && <Loading />}
        {data && decks.length === 0 && (
          <p className="empty">
            Chưa có thẻ nào. Thẻ ôn được tạo từ những câu bạn trả lời sai trong
            Luyện tập và Thi thử.
          </p>
        )}
        {decks.length > 0 && (
          <>
            <section className="card stack" aria-labelledby="decks-today">
              <h2 id="decks-today" className="label">
                Hôm nay
              </h2>
              <div className="row" style={{ alignItems: "flex-start" }}>
                <Stat
                  value={sum((d) => d.new)}
                  label="Mới"
                  color="var(--new)"
                />
                <Stat
                  value={sum((d) => d.learning)}
                  label="Đang học"
                  color="var(--learning-dark)"
                />
                <Stat value={due} label="Đến hạn" color="var(--primary-dark)" />
              </div>
              {due > 0 && (
                <Link to="/luyen-tap/on-the" className="btn primary lg block">
                  Ôn {due} thẻ
                </Link>
              )}
            </section>
            <table className="list counts" aria-label="Bộ thẻ theo học phần">
              <thead>
                <tr>
                  <th scope="col">Bộ thẻ</th>
                  <th scope="col">Mới</th>
                  <th scope="col">Học</th>
                  <th scope="col">Ôn</th>
                </tr>
              </thead>
              <tbody>
                {decks.map((d) => (
                  <tr key={d.module_id}>
                    <th scope="row">{d.short_name}</th>
                    <td style={{ color: "var(--new)" }}>{d.new}</td>
                    <td style={{ color: "var(--learning-dark)" }}>
                      {d.learning}
                    </td>
                    <td style={{ color: "var(--primary-dark)" }}>{d.due}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
      <TabBar />
    </div>
  );
}

function Stat({
  value,
  label,
  color,
}: {
  value: number;
  label: string;
  color: string;
}) {
  return (
    <div className="grow">
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      <div className="muted small">{label}</div>
    </div>
  );
}
