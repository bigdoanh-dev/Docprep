import { useState } from "react";
import { BookOpen, FileText, Search, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import {
  api,
  type Listed,
  type Module,
  type ModuleDetail,
} from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { LoadError, Loading } from "../../components/Status";
const references = [
  {
    title: "Hệ thống văn bản ngành y tế",
    type: "Văn bản Bộ Y tế",
    specialty: "Y học dự phòng",
    url: "https://vnpa.moh.gov.vn/he-thong-van-ban/",
    description: "Tra cứu văn bản và quyết định tại cơ quan thuộc Bộ Y tế.",
  },
  {
    title: "Hướng dẫn chẩn đoán và điều trị loét bàn chân do đái tháo đường",
    type: "Hướng dẫn điều trị",
    specialty: "Nội khoa",
    url: "https://kcb.vn/upload/2005611/20230421/QD_2023_1530_Quyet_dinh_ban_hanh_tai_lieu_chuyen_mon__Huong_dan_chan_doan_va_dieu_tri_Loet_ban_chan_do_dai_thao_duong__25013.pdf",
    description: "Tài liệu chuyên môn do Bộ Y tế ban hành năm 2023.",
  },
  {
    title: "WHO Guidelines",
    type: "Guideline quốc tế",
    specialty: "Đa chuyên khoa",
    url: "https://www.who.int/publications/who-guidelines",
    description: "Cổng hướng dẫn chuyên môn của Tổ chức Y tế Thế giới.",
  },
  {
    title: "WHO consolidated guidelines on tuberculosis",
    type: "Guideline quốc tế",
    specialty: "Bệnh truyền nhiễm",
    url: "https://www.who.int/publications/i/item/9789240125124",
    description:
      "Module 4: treatment and care, 2nd edition, 2026. Tài liệu gốc bằng tiếng Anh.",
  },
];
export function Resources() {
  const [tab, setTab] = useState("study"),
    [search, setSearch] = useState(""),
    [specialty, setSpecialty] = useState("all");
  const { data, error, reload } = useLoad(async () => {
    const modules = await api.get<Listed<Module>>("/modules");
    const details = await Promise.all(
      modules.items
        .filter((m) => !m.coming_soon)
        .map((m) => api.get<ModuleDetail>(`/modules/${m.id}`)),
    );
    return details.flatMap((m) =>
      m.units.map((u) => ({ ...u, specialty: m.short_name })),
    );
  }, []);
  const match = (s: string) =>
    s.toLocaleLowerCase("vi").includes(search.toLocaleLowerCase("vi"));
  const rows = references.filter(
    (r) =>
      match(`${r.title} ${r.specialty} ${r.type}`) &&
      (specialty === "all" || specialty === r.specialty),
  );
  return (
    <div className="screen stack">
      <header className="page-heading">
        <h1>Thư viện tài liệu</h1>
        <p>Bài giảng ôn tập và tài liệu tham khảo từ nguồn chuyên môn.</p>
      </header>
      <div className="segmented">
        <button
          className={tab === "study" ? "active" : ""}
          onClick={() => setTab("study")}
        >
          Tài liệu ôn tập
        </button>
        <button
          className={tab === "reference" ? "active" : ""}
          onClick={() => setTab("reference")}
        >
          Tài liệu tham khảo
        </button>
      </div>
      <div className="module-toolbar">
        <label className="search-field">
          <Search size={19} />
          <input
            aria-label="Tìm tài liệu"
            placeholder="Tìm bài giảng, chủ đề hoặc guideline…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        {tab === "reference" && (
          <select
            aria-label="Lọc theo chuyên khoa"
            value={specialty}
            onChange={(e) => setSpecialty(e.target.value)}
          >
            <option value="all">Tất cả chuyên khoa</option>
            {[...new Set(references.map((r) => r.specialty))].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        )}
      </div>
      {tab === "study" ? (
        <>
          <p className="notice">
            Các bài giảng hiện có dùng học liệu minh họa, chưa thẩm định. Bài
            tóm tắt theo các chuyên khoa khác đang xây dựng.
          </p>
          {error && <LoadError message={error} onRetry={reload} />}
          {!data && !error && <Loading />}
          {data
            ?.filter((u) => match(u.topic))
            .map((u) => (
              <Link
                key={u.id}
                to={`/luyen-tap/${u.id}`}
                className="resource-row"
              >
                <BookOpen />
                <div>
                  <span className="muted small">{u.specialty}</span>
                  <h2>{u.topic}</h2>
                  <p>Bài giảng, nội dung ôn tập và câu hỏi củng cố</p>
                </div>
                <span className="btn">Mở bài giảng</span>
              </Link>
            ))}
          {data && !data.filter((u) => match(u.topic)).length && (
            <p className="empty">Không tìm thấy bài giảng phù hợp.</p>
          )}
        </>
      ) : (
        <>
          <p className="muted">
            Liên kết mở tài liệu gốc tại cơ quan phát hành. Kiểm tra phiên bản
            và hiệu lực trên nguồn trước khi sử dụng.
          </p>
          {rows.map((r) => (
            <a
              key={r.url}
              href={r.url}
              target="_blank"
              rel="noreferrer"
              className="resource-row"
            >
              <FileText />
              <div>
                <span className="muted small">
                  {r.type} · {r.specialty}
                </span>
                <h2>{r.title}</h2>
                <p>{r.description}</p>
              </div>
              <ExternalLink size={20} />
            </a>
          ))}
          {!rows.length && (
            <p className="empty">Không tìm thấy tài liệu phù hợp.</p>
          )}
        </>
      )}
    </div>
  );
}
