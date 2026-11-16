import { useCallback, useEffect, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  api,
  download,
  saveSession,
  session,
  write,
  type Session,
} from "./client";
import "./style.css";

type Tags = {
  taxonomy_version: string;
  source: string;
  van_de: { id: number; primary: boolean; conf?: number }[];
  mien: { id: string; conf?: number }[];
  bloom_ceiling: { level: string };
  content_type: string;
  population: string[];
  ly_do: string;
};
type Chunk = {
  id: string;
  source_chunk_id: string;
  title: string;
  external_doc_id: string;
  preview: string;
  classification_status: string;
  content_status: string;
  classification_policy: string | null;
  content_policy: string | null;
  row_version: number;
  kind: string;
  text: string;
  location: { section_path: string[]; printed_pages?: string[] };
  source_availability: string;
  quality_flags: string[];
  proposed_tags: Tags | null;
  confirmed_tags: Tags | null;
  tasks: { purpose: string; reasons: string[] }[];
  decisions: {
    id: string;
    purpose: string;
    decision: string;
    display_name: string;
    comment: string;
    created_at: string;
  }[];
  assets: { id: string; asset_key: string; mime_type: string }[];
};
type Taxonomy = {
  version: string;
  mapping: { approved?: boolean };
  payload: {
    van_de: { id: number; name: string }[];
    mien: { sub: { id: string; name: string }[] }[];
  };
};
type Catalog = {
  items: Taxonomy[];
  content_types: string[];
  populations: string[];
  bloom: string[];
};
type Listing = { items: Chunk[]; total: number; classified: number };
type Doc = {
  id: string;
  external_doc_id: string;
  title: string;
  chunks: number;
};
const labels: Record<string, string> = {
  classified: "Đã phân loại rõ ràng",
  unclassified: "Chưa phân loại / xác nhận",
  pending: "Chờ duyệt nội dung",
  approved: "Nội dung đã duyệt",
  needs_revision: "Cần sửa nội dung",
  rejected: "Nội dung bị từ chối",
};
const message = (e: unknown) =>
  e instanceof Error ? e.message : "Không thể hoàn thành thao tác.";
const provisional = (c: Chunk) =>
  c.classification_policy === "source-baseline-v1" ||
  c.content_policy === "source-baseline-v1";

function Login({ onLogin }: { onLogin: (value: Session) => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const result = await api<Session>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: data.get("username"),
          password: data.get("password"),
        }),
      });
      saveSession(result);
      onLogin(result);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="content-login">
      <p className="eyebrow">YHDP · CONTENT WORKSPACE</p>
      <h1>Kho tài liệu</h1>
      <p>Đăng nhập dành cho đội biên soạn và thẩm định nội dung.</p>
      <form onSubmit={submit}>
        <label>
          Tên đăng nhập
          <input name="username" autoComplete="username" required />
        </label>
        <label>
          Mật khẩu
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button disabled={busy}>
          {busy ? "Đang đăng nhập…" : "Đăng nhập"}
        </button>
      </form>
      <p className="muted">
        Tài khoản content được cấp riêng. Tài khoản người học không đăng nhập
        tại đây.
      </p>
    </main>
  );
}

function Editor({
  chunk,
  catalog,
  canEdit,
  onSave,
}: {
  chunk: Chunk;
  catalog: Catalog;
  canEdit: boolean;
  onSave: (body: unknown) => Promise<void>;
}) {
  const t = chunk.proposed_tags;
  const [taxonomy, setTaxonomy] = useState(
    t?.taxonomy_version || catalog.items[0]?.version || "",
  );
  const [primary, setPrimary] = useState(
    t?.van_de.find((v) => v.primary)?.id || 1,
  );
  const [secondary, setSecondary] = useState<number[]>(
    t?.van_de.filter((v) => !v.primary).map((v) => v.id) || [],
  );
  const [domains, setDomains] = useState<string[]>(
    t?.mien.map((v) => v.id) || [],
  );
  const [bloom, setBloom] = useState(t?.bloom_ceiling.level || "Nhớ");
  const [kind, setKind] = useState(t?.content_type || "khác");
  const [population, setPopulation] = useState(t?.population || []);
  const [reason, setReason] = useState(t?.ly_do || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selected = catalog.items.find((x) => x.version === taxonomy);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSave({
        row_version: chunk.row_version,
        taxonomy_version: taxonomy,
        tags: {
          van_de: [
            { id: primary, primary: true },
            ...secondary
              .filter((id) => id !== primary)
              .map((id) => ({ id, primary: false })),
          ],
          mien: domains.map((id) => ({ id })),
          bloom_ceiling: { level: bloom },
          content_type: kind,
          population,
          ly_do: reason,
        },
      });
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="tag-form" onSubmit={submit}>
      <h3>Bộ nhãn đề xuất</h3>
      <p className="muted">
        Nguồn nhãn:{" "}
        {t?.source === "auto"
          ? "Tự động từ YHDP, chưa phải xác nhận chuyên gia"
          : "Biên soạn thủ công"}
      </p>
      <fieldset disabled={!canEdit || busy}>
        <label>
          Taxonomy
          <select
            value={taxonomy}
            onChange={(e) => setTaxonomy(e.target.value)}
          >
            {catalog.items.map((v) => (
              <option key={v.version} value={v.version}>
                {v.version}
                {v.mapping.approved ? " · có mapping" : " · chưa mapping"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Vấn đề chính
          <select
            value={primary}
            onChange={(e) => {
              setPrimary(Number(e.target.value));
              setSecondary((v) =>
                v.filter((id) => id !== Number(e.target.value)),
              );
            }}
          >
            {selected?.payload.van_de.map((v) => (
              <option key={v.id} value={v.id}>
                {v.id}. {v.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Vấn đề phụ (tối đa 2)
          <select
            multiple
            value={secondary.map(String)}
            onChange={(e) =>
              setSecondary(
                Array.from(e.target.selectedOptions, (x) => Number(x.value)),
              )
            }
          >
            {selected?.payload.van_de
              .filter((v) => v.id !== primary)
              .map((v) => (
                <option key={v.id} value={v.id}>
                  {v.id}. {v.name}
                </option>
              ))}
          </select>
        </label>
        <label>
          Miền năng lực (1–2)
          <select
            multiple
            value={domains}
            onChange={(e) =>
              setDomains(Array.from(e.target.selectedOptions, (x) => x.value))
            }
          >
            {selected?.payload.mien
              .flatMap((v) => v.sub)
              .map((v) => (
                <option key={v.id} value={v.id}>
                  {v.id} · {v.name}
                </option>
              ))}
          </select>
        </label>
        <div className="form-row">
          <label>
            Bloom trần
            <select value={bloom} onChange={(e) => setBloom(e.target.value)}>
              {catalog.bloom.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Loại nội dung
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {catalog.content_types.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Đối tượng
          <select
            multiple
            value={population}
            onChange={(e) =>
              setPopulation(
                Array.from(e.target.selectedOptions, (x) => x.value),
              )
            }
          >
            {catalog.populations.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Lý do phân loại
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            maxLength={6000}
          />
        </label>
        {canEdit && (
          <button
            disabled={
              busy ||
              secondary.length > 2 ||
              domains.length < 1 ||
              domains.length > 2 ||
              population.length > 3
            }
          >
            Lưu đề xuất nhãn
          </button>
        )}
      </fieldset>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </form>
  );
}

function Workspace({ user, logout }: { user: Session; logout: () => void }) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [classification, setClassification] = useState("");
  const [doc, setDoc] = useState("");
  const [offset, setOffset] = useState(0);
  const [listing, setListing] = useState<Listing>({
    items: [],
    total: 0,
    classified: 0,
  });
  const [selected, setSelected] = useState("");
  const [chunk, setChunk] = useState<Chunk | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [chosen, setChosen] = useState<string[]>([]);
  const [version, setVersion] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const editor = user.roles.includes("editor"),
    reviewer = user.roles.includes("reviewer"),
    publisher = user.roles.includes("publisher");
  useEffect(() => {
    const c = new AbortController();
    Promise.all([
      api<{ items: Doc[] }>("/documents", { signal: c.signal }),
      api<Catalog>("/taxonomies", { signal: c.signal }),
      api("/me", { signal: c.signal }),
    ])
      .then(([d, t]) => {
        setDocs(d.items);
        setCatalog(t);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(message(e));
      });
    return () => c.abort();
  }, [revision]);
  useEffect(() => {
    const c = new AbortController();
    const q = new URLSearchParams({ offset: String(offset), limit: "25" });
    if (classification) q.set("classification", classification);
    if (doc) q.set("document", doc);
    api<Listing>(`/chunks?${q}`, { signal: c.signal })
      .then(setListing)
      .catch((e) => {
        if (!c.signal.aborted) setError(message(e));
      });
    return () => c.abort();
  }, [classification, doc, offset, revision]);
  useEffect(() => {
    if (!selected) return;
    const c = new AbortController();
    setChunk(null);
    setNotice("");
    setComment("");
    api<Chunk>(`/chunks/${selected}`, { signal: c.signal })
      .then(setChunk)
      .catch((e) => {
        if (!c.signal.aborted) setError(message(e));
      });
    return () => c.abort();
  }, [selected, revision]);
  useEffect(
    () => () => {
      if (image) URL.revokeObjectURL(image);
    },
    [image],
  );
  const refresh = useCallback(() => {
    setError("");
    setRevision((x) => x + 1);
  }, []);
  async function decide(purpose: string, decision: string) {
    if (!chunk) return;
    setBusy(true);
    setError("");
    try {
      await write(
        `/chunks/${chunk.id}/decisions`,
        { row_version: chunk.row_version, purpose, decision, comment },
        crypto.randomUUID(),
      );
      refresh();
      setNotice("Quyết định đã được lưu trên server.");
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function asset(id: string) {
    try {
      const r = await fetch(`/api/v1/assets/${id}`, {
        headers: { Authorization: `Bearer ${session()?.access_token}` },
      });
      if (!r.ok) throw new Error("Không mở được file nguồn.");
      const blob = await r.blob();
      if (blob.type.startsWith("image/")) setImage(URL.createObjectURL(blob));
      else download("source-artifact", blob);
    } catch (e) {
      setError(message(e));
    }
  }
  async function release() {
    setBusy(true);
    setError("");
    try {
      const data = await api("/releases/export", {
        method: "POST",
        body: JSON.stringify({ version, chunk_ids: chosen }),
      });
      download(
        `${version}.json`,
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      setNotice("Đã xuất gói local/dev. Gói chưa tự kích hoạt trong runtime.");
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="content-header">
        <div>
          <p className="eyebrow">CONTENT WORKSPACE · LOCAL/DEV</p>
          <h1>Biên soạn tài liệu YHDP</h1>
        </div>
        <div>
          <p>
            {user.display_name} · {user.roles.join(", ")}
          </p>
          <button className="secondary" onClick={logout}>
            Đăng xuất
          </button>
        </div>
      </header>
      <main className="workspace">
        <div className="toolbar">
          <label>
            Trạng thái phân loại
            <select
              value={classification}
              onChange={(e) => {
                setClassification(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Cả hai nhóm</option>
              <option value="unclassified">Chưa phân loại / xác nhận</option>
              <option value="classified">Đã phân loại rõ ràng</option>
            </select>
          </label>
          <label>
            Tài liệu
            <select
              value={doc}
              onChange={(e) => {
                setDoc(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Tất cả tài liệu</option>
              {docs.map((d) => (
                <option key={d.id} value={d.external_doc_id}>
                  {d.title} · {d.chunks} chunk
                </option>
              ))}
            </select>
          </label>
          <button className="secondary" onClick={refresh}>
            Tải lại dữ liệu
          </button>
        </div>
        <p className="muted">
          {listing.total} chunk trong danh sách · {listing.classified} đã xác
          nhận. Nhãn tự động chỉ là đề xuất; phân loại và duyệt nội dung là hai
          việc riêng.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
        <div className="workspace-grid">
          <section className="chunk-list" aria-label="Danh sách chunk">
            <div
              className="chunk-list-items"
              key={`${doc}:${classification}:${offset}`}
              role="region"
              aria-label="Các đoạn tài liệu"
              tabIndex={0}
            >
              {listing.items.map((c) => (
                <article
                  className={selected === c.id ? "selected" : ""}
                  key={c.id}
                >
                  {publisher && (
                    <label className="select-release">
                      <input
                        type="checkbox"
                        aria-label={`Chọn xuất ${c.source_chunk_id}`}
                        checked={chosen.includes(c.id)}
                        onChange={(e) =>
                          setChosen((v) =>
                            e.target.checked
                              ? [...v, c.id]
                              : v.filter((x) => x !== c.id),
                          )
                        }
                      />{" "}
                      Chọn xuất release
                    </label>
                  )}
                  <button
                    className="chunk-link"
                    onClick={() => setSelected(c.id)}
                  >
                    <strong>{c.source_chunk_id}</strong>
                    <span className={`badge ${c.classification_status}`}>
                      {labels[c.classification_status]}
                    </span>
                    <span>{c.preview}</span>
                    <small>{labels[c.content_status]}</small>
                    {provisional(c) && (
                      <small>Chấp nhận tạm theo dữ liệu nguồn</small>
                    )}
                  </button>
                </article>
              ))}
              {listing.total === 0 && (
                <p>
                  Chưa có chunk phù hợp. Nhập dữ liệu bằng importer hoặc đổi bộ
                  lọc.
                </p>
              )}
            </div>
            <nav className="pagination" aria-label="Phân trang">
              <button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 25))}
              >
                Trước
              </button>
              <span>
                {offset + 1}–{Math.min(offset + 25, listing.total)}
              </span>
              <button
                disabled={offset + 25 >= listing.total}
                onClick={() => setOffset(offset + 25)}
              >
                Sau
              </button>
            </nav>
          </section>
          <section className="chunk-detail" aria-label="Chi tiết chunk">
            {chunk && catalog ? (
              <>
                <p className="eyebrow">
                  {chunk.external_doc_id} · {chunk.kind}
                </p>
                <h2>{chunk.source_chunk_id}</h2>
                <p>{chunk.location.section_path.join(" › ")}</p>
                <p className="source-note">
                  Nguồn:{" "}
                  {chunk.source_availability === "derived_only"
                    ? "Dữ liệu dẫn xuất; chưa kèm file gốc"
                    : chunk.source_availability}
                  . Version thao tác: {chunk.row_version}.
                </p>
                <div className="badges">
                  <span className="badge">
                    {labels[chunk.classification_status]}
                  </span>
                  <span className="badge">{labels[chunk.content_status]}</span>
                </div>
                {provisional(chunk) && (
                  <p className="source-note" role="note">
                    Chấp nhận tạm theo data.zip để phát triển. Chưa thẩm định
                    chuyên môn; có thể sửa nhãn hoặc yêu cầu rà soát lại bên
                    dưới.
                  </p>
                )}
                <div className="chunk-text">
                  <Markdown remarkPlugins={[remarkGfm]}>{chunk.text}</Markdown>
                </div>
                <details>
                  <summary>Cờ và lý do cần kiểm tra</summary>
                  <pre>
                    {JSON.stringify(
                      { flags: chunk.quality_flags, tasks: chunk.tasks },
                      null,
                      2,
                    )}
                  </pre>
                </details>
                <details>
                  <summary>File và ảnh nguồn ({chunk.assets.length})</summary>
                  {chunk.assets.map((a) => (
                    <button
                      className="asset-link"
                      key={a.id}
                      onClick={() => asset(a.id)}
                    >
                      {a.asset_key}
                    </button>
                  ))}
                </details>
                <Editor
                  key={`${chunk.id}:${chunk.row_version}`}
                  chunk={chunk}
                  catalog={catalog}
                  canEdit={editor}
                  onSave={async (body) => {
                    await write(
                      `/chunks/${chunk.id}/tags`,
                      body,
                      crypto.randomUUID(),
                    );
                    refresh();
                  }}
                />
                {reviewer && (
                  <section className="review-panel">
                    <h3>Xác nhận và duyệt</h3>
                    <label>
                      Nhận xét / nội dung đã kiểm tra
                      <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        maxLength={4000}
                        rows={3}
                        placeholder="Ghi rõ căn cứ xác nhận; cách xử lý lỗi bảng/hình hoặc nguồn dẫn xuất nếu có."
                      />
                    </label>
                    <div className="review-actions">
                      <button
                        disabled={
                          busy || !comment.trim() || !chunk.proposed_tags
                        }
                        onClick={() => decide("classification", "accept")}
                      >
                        Xác nhận phân loại
                      </button>
                      <button
                        disabled={busy || !comment.trim()}
                        onClick={() => decide("content", "accept")}
                      >
                        Duyệt nội dung
                      </button>
                      <button
                        className="secondary"
                        disabled={busy || !comment.trim()}
                        onClick={() => decide("classification", "revise")}
                      >
                        Cần sửa nhãn
                      </button>
                      <button
                        className="secondary"
                        disabled={busy || !comment.trim()}
                        onClick={() => decide("content", "revise")}
                      >
                        Cần sửa nội dung
                      </button>
                      <button
                        className="danger"
                        disabled={busy || !comment.trim()}
                        onClick={() => decide("content", "reject")}
                      >
                        Từ chối nội dung
                      </button>
                    </div>
                  </section>
                )}
                <section>
                  <h3>Lịch sử quyết định</h3>
                  {chunk.decisions.length ? (
                    chunk.decisions.map((d) => (
                      <article className="decision" key={d.id}>
                        <strong>
                          {d.display_name} ·{" "}
                          {d.purpose === "classification"
                            ? "Phân loại"
                            : "Nội dung"}{" "}
                          · {d.decision}
                        </strong>
                        <p>{d.comment}</p>
                        <small>
                          {new Date(d.created_at).toLocaleString("vi-VN")}
                        </small>
                      </article>
                    ))
                  ) : (
                    <p className="muted">Chưa có quyết định xác nhận.</p>
                  )}
                </section>
              </>
            ) : (
              <div className="empty">
                <h2>Chọn một chunk để thẩm định</h2>
                <p>
                  Xem nguồn, sửa nhãn và ghi quyết định. Dữ liệu được lưu ở DB
                  tài liệu riêng.
                </p>
              </div>
            )}
          </section>
        </div>
        {publisher && (
          <section className="release-panel">
            <h2>Xuất gói local/dev</h2>
            <p>
              Đã chọn {chosen.length} chunk. Chỉ xuất được khi từng chunk đã xác
              nhận nhãn, duyệt nội dung và có mapping được duyệt. Việc đưa vào
              runtime thực hiện bằng publisher CLI.
            </p>
            <div className="form-row">
              <label>
                Version release
                <input
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  placeholder="yhdp-dev-2026-11-16"
                />
              </label>
              <button
                disabled={
                  busy ||
                  !chosen.length ||
                  !/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$/.test(version)
                }
                onClick={release}
              >
                Xuất manifest
              </button>
            </div>
          </section>
        )}
        {image && (
          <div
            className="image-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Ảnh nguồn"
          >
            <button onClick={() => setImage(null)}>Đóng ảnh</button>
            <img src={image} alt="Ảnh trong tài liệu nguồn" />
          </div>
        )}
      </main>
    </>
  );
}

function App() {
  const [user, setUser] = useState<Session | null>(session);
  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener("content-auth-expired", expired);
    return () => window.removeEventListener("content-auth-expired", expired);
  }, []);
  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      saveSession(null);
      setUser(null);
    }
  }
  return user ? (
    <Workspace user={user} logout={logout} />
  ) : (
    <Login onLogin={setUser} />
  );
}
createRoot(document.getElementById("root")!).render(<App />);
