import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { AssessmentRadar } from "../../components/Charts";
import {
  BLOOM,
  assessmentPercent,
  learningMatrix,
  type AnalysisPerspective,
  type AssessmentCount,
  type BloomSpecialty,
} from "../../lib/learningAnalytics";

type Props = {
  specialties?: (AssessmentCount & { name: string })[];
  levels: (AssessmentCount & { level: number; label_vi: string })[];
  bySpecialty?: BloomSpecialty[];
};

export function SpecialtyAnalysis({ specialties, levels, bySpecialty }: Props) {
  const headingId = useId();
  const [perspective, setPerspective] =
    useState<AnalysisPerspective>("specialty");
  const [selected, setSelected] = useState("all");
  const [tableView, setTableView] = useState<"compact" | "full">("compact");
  const [selectedRow, setSelectedRow] = useState("");
  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const groups = bySpecialty ?? [];
  // A scope change can remove a group; fall back to all instead of showing stale data.
  const activeGroup = groups.find((g) => g.module_id === selected);
  const shownGroups = activeGroup ? [activeGroup] : groups;
  const shownLevels = activeGroup?.levels ?? levels;
  const specialtyCounts =
    specialties ??
    groups.map((g) => ({
      name: g.name,
      correct: g.levels.reduce((sum, l) => sum + l.correct, 0),
      total: g.levels.reduce((sum, l) => sum + l.total, 0),
    }));
  const axes =
    perspective === "specialty"
      ? specialtyCounts.map((s, i) => ({
          ...s,
          id: String(i),
          name: s.name,
          label: `Nhóm ${i + 1}`,
        }))
      : BLOOM.map((label, i) => ({
          id: String(i + 1),
          name: label,
          label,
          correct: shownLevels.find((l) => l.level === i + 1)?.correct ?? 0,
          total: shownLevels.find((l) => l.level === i + 1)?.total ?? 0,
        }));
  const matrix = learningMatrix(
    perspective === "bloom" ? shownGroups : groups,
    perspective,
  );
  const activeRow =
    matrix.rows.find((r) => r.id === selectedRow) ??
    matrix.rows.find((r) => r.cells.some((c) => c.total > 0)) ??
    matrix.rows[0];
  const cell = matrix.rows
    .flatMap((row) => row.cells)
    .find((c) => c.id === selectedCell);
  const hasAssessment = axes.some((a) => a.total > 0);
  const title =
    perspective === "specialty"
      ? "Kết quả theo chuyên khoa"
      : "Mức độ hiểu và vận dụng";

  function changePerspective(next: AnalysisPerspective) {
    setPerspective(next);
    setSelected("all");
    setSelectedCell(null);
    setSelectedRow("");
  }

  return (
    <section
      className="panel stack learning-matrix mobile-analysis"
      aria-labelledby={headingId}
    >
      <div className="matrix-heading">
        <div>
          <h2 id={headingId}>Điểm mạnh và phần cần ôn</h2>
          <p className="muted small">
            Tỷ lệ câu đúng từ các bài thi thử đã nộp.
          </p>
        </div>
        <div
          className="matrix-switch"
          role="group"
          aria-label="Góc nhìn thống kê"
        >
          <button
            type="button"
            aria-pressed={perspective === "specialty"}
            onClick={() => changePerspective("specialty")}
          >
            Theo chuyên khoa
          </button>
          <button
            type="button"
            aria-pressed={perspective === "bloom"}
            onClick={() => changePerspective("bloom")}
          >
            Mức độ vận dụng
          </button>
        </div>
      </div>
      {perspective === "bloom" && groups.length > 0 && (
        <label className="field matrix-filter">
          Xem mức độ vận dụng theo chuyên khoa
          <select
            value={activeGroup?.module_id ?? "all"}
            onChange={(e) => {
              setSelected(e.target.value);
              setSelectedCell(null);
            }}
          >
            <option value="all">Tất cả chuyên khoa</option>
            {groups.map((g) => (
              <option key={g.module_id} value={g.module_id}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="analysis-section">
        <div className="analysis-view-heading">
          <h3>{title}</h3>
        </div>
        <div className="assessment-combined">
          {axes.length >= 3 ? (
            <AssessmentRadar
              axes={axes}
              label={`Biểu đồ radar ${title.toLowerCase()}; tỷ lệ và số lượt câu đúng được trình bày trong danh sách ngay bên dưới.`}
            />
          ) : (
            <p className="muted small">Chưa đủ nhóm dữ liệu để vẽ radar.</p>
          )}
          <ol
            className="assessment-bars"
            aria-label={`Chi tiết ${title.toLowerCase()}`}
          >
            {axes.map((a) => {
              const pct = assessmentPercent(a);
              return (
                <li key={a.id} className={pct === null ? "not-assessed" : ""}>
                  <div className="assessment-bar-heading">
                    <span>
                      {perspective === "specialty" ? `${a.label} · ` : ""}
                      {a.name}
                    </span>
                    <strong>{pct === null ? "—" : `${pct}%`}</strong>
                  </div>
                  {pct !== null ? (
                    <>
                      <div className="progress" aria-hidden="true">
                        <span style={{ width: `${pct}%` }} />
                      </div>
                      <small>
                        {a.correct}/{a.total} lượt câu đúng
                      </small>
                    </>
                  ) : (
                    <span className="sr">Chưa có dữ liệu</span>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
        <p className="muted small">“—” là chưa có dữ liệu, không phải 0%.</p>
        {!hasAssessment && (
          <p className="matrix-empty">
            Chưa có kết quả trong phạm vi đang chọn.{" "}
            <Link to="/thi-thu">Làm bài thi thử</Link> để bổ sung dữ liệu.
          </p>
        )}
      </div>
      <div className="analysis-section">
        <div className="analysis-view-heading">
          <h3>Chi tiết kết quả</h3>
          <div
            className="analysis-view-switch"
            role="group"
            aria-label="Cách xem bảng"
          >
            <button
              type="button"
              aria-pressed={tableView === "compact"}
              onClick={() => setTableView("compact")}
            >
              Thu gọn
            </button>
            <button
              type="button"
              aria-pressed={tableView === "full"}
              onClick={() => setTableView("full")}
            >
              Bảng đầy đủ
            </button>
          </div>
        </div>
        {matrix.rows.length > 0 && matrix.columns.length > 0 ? (
          <>
            {tableView === "compact" && activeRow && (
              <div className="compact-results">
                <label className="field">
                  {perspective === "specialty"
                    ? "Chuyên khoa"
                    : "Mức độ vận dụng"}
                  <select
                    value={activeRow.id}
                    onChange={(e) => {
                      setSelectedRow(e.target.value);
                      setSelectedCell(null);
                    }}
                  >
                    {matrix.rows.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="compact-results-head">
                  <span>
                    {perspective === "specialty"
                      ? "Mức độ vận dụng"
                      : "Chuyên khoa"}
                  </span>
                  <span>Đúng / lượt câu</span>
                  <span>Tỷ lệ</span>
                </div>
                <div
                  className="compact-result-list"
                  aria-label={`Kết quả chi tiết ${activeRow.label}`}
                >
                  {activeRow.cells.map((c) => {
                    const pct = assessmentPercent(c);
                    return (
                      <button
                        type="button"
                        key={c.id}
                        aria-pressed={c.id === cell?.id}
                        aria-label={`${c.specialty}, ${c.bloom}: ${pct === null ? "chưa có dữ liệu" : `${pct}%, ${c.correct}/${c.total} lượt câu đúng`}`}
                        onClick={() => setSelectedCell(c.id)}
                      >
                        <span>
                          {perspective === "specialty" ? c.bloom : c.specialty}
                        </span>
                        <span>
                          {c.total ? `${c.correct}/${c.total}` : "Chưa có"}
                        </span>
                        <strong>{pct === null ? "—" : `${pct}%`}</strong>
                      </button>
                    );
                  })}
                </div>
                <p className="muted small">
                  Chạm một dòng để xem chi tiết. “—” là chưa có dữ liệu.
                </p>
              </div>
            )}
            {tableView === "full" && (
              <>
                <p className="muted small">
                  Vuốt ngang để xem các cột. Chạm ô để xem số lượt câu đúng.
                </p>
                <div
                  className="matrix-table-scroll"
                  tabIndex={0}
                  role="region"
                  aria-label="Ma trận chuyên khoa và mức độ vận dụng, có thể cuộn ngang"
                >
                  <table className="assessment-matrix">
                    <caption className="sr">
                      Tỷ lệ đúng và số lượt câu theo chuyên khoa và sáu mức độ
                      từ ghi nhớ đến vận dụng. Dấu gạch ngang là chưa có dữ
                      liệu.
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">
                          {perspective === "specialty"
                            ? "Chuyên khoa / nhóm năng lực"
                            : "Mức nhận thức"}
                        </th>
                        {matrix.columns.map((col) => (
                          <th key={col.id} scope="col">
                            {col.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {matrix.rows.map((row) => (
                        <tr key={row.id}>
                          <th scope="row">{row.label}</th>
                          {row.cells.map((c) => {
                            const pct = assessmentPercent(c);
                            return (
                              <td key={c.id}>
                                <button
                                  type="button"
                                  className={`matrix-cell matrix-tone-${pct === null ? "empty" : Math.min(4, Math.floor(pct / 25))}`}
                                  aria-pressed={c.id === cell?.id}
                                  aria-label={`${c.specialty}, ${c.bloom}: ${pct === null ? "chưa có dữ liệu" : `${pct}%, ${c.correct}/${c.total} lượt câu đúng`}`}
                                  onClick={() => setSelectedCell(c.id)}
                                >
                                  <strong>
                                    {pct === null ? "—" : `${pct}%`}
                                  </strong>
                                  <span>
                                    {pct === null
                                      ? "Chưa có dữ liệu"
                                      : `${c.correct}/${c.total}`}
                                  </span>
                                </button>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {cell && (
              <div className="matrix-detail" role="status" aria-live="polite">
                <strong>
                  {cell.specialty} · {cell.bloom}
                </strong>
                <p>
                  {cell.total
                    ? `${cell.correct}/${cell.total} lượt câu đúng (${assessmentPercent(cell)}%). ${cell.total - cell.correct} lượt chưa đúng hoặc bỏ trống.`
                    : "Chưa có câu được đánh giá ở mức nhận thức này trong phạm vi đang chọn."}
                </p>
              </div>
            )}
          </>
        ) : (
          <p className="matrix-empty">
            Chưa đủ kết quả để xem theo chuyên khoa và mức độ vận dụng. Khi bạn
            hoàn thành thêm bài, bảng sẽ hiển thị tại đây.
          </p>
        )}
      </div>
    </section>
  );
}
