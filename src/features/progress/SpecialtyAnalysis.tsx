import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { AssessmentRadar } from "../../components/Charts";
import blueprint from "../../lib/blueprint.json";
import {
  BLOOM,
  assessmentPercent,
  learningMatrix,
  type AnalysisPerspective,
  type AssessmentCount,
  type BloomSpecialty,
  type SpecialtyIssues,
} from "../../lib/learningAnalytics";

type Props = {
  specialties?: (AssessmentCount & { name: string; module_id?: string })[];
  levels: (AssessmentCount & { level: number; label_vi: string })[];
  bySpecialty?: BloomSpecialty[];
  byIssue?: SpecialtyIssues[];
};

export function SpecialtyAnalysis({
  specialties,
  levels,
  bySpecialty,
  byIssue,
}: Props) {
  const headingId = useId();
  const [perspective, setPerspective] =
    useState<AnalysisPerspective>("specialty");
  const [selected, setSelected] = useState("all");
  const [tableView, setTableView] = useState<"compact" | "full">("compact");
  const [selectedRow, setSelectedRow] = useState("");
  const [selectedCell, setSelectedCell] = useState<string | null>(null);
  const [selectedAxisId, setSelectedAxisId] = useState<string | null>(null);
  const groups = bySpecialty ?? [];
  // A scope change can remove a group; fall back to all instead of showing stale data.
  const activeSpecialty = blueprint.groups.find((g) => `g${g.id}` === selected);
  const activeGroup = groups.find((g) => g.module_id === selected);
  const shownGroups = activeGroup ? [activeGroup] : groups;
  const shownLevels = activeGroup?.levels ?? levels;
  const specialtyCounts =
    specialties ??
    groups.map((g) => ({
      module_id: g.module_id,
      name: g.name,
      correct: g.levels.reduce((sum, l) => sum + l.correct, 0),
      total: g.levels.reduce((sum, l) => sum + l.total, 0),
    }));
  const issueCounts =
    byIssue?.find((g) => g.module_id === selected)?.issues ?? [];
  const axes =
    perspective === "specialty" && activeSpecialty
      ? activeSpecialty.issues.map((issue, index) => {
          const count = issueCounts.find((i) => i.issue_id === issue.id);
          return {
            id: `CI-${issue.id}`,
            number: index + 1,
            name: issue.name,
            label: String(index + 1),
            correct: count?.correct ?? 0,
            total: count?.total ?? 0,
          };
        })
      : perspective === "specialty"
        ? blueprint.groups.map((group) => {
            const count = specialtyCounts.find(
              (s) =>
                s.module_id === `g${group.id}` ||
                s.name === group.short_name ||
                s.name === group.name,
            );
            return {
              id: String(group.id),
              number: group.id,
              name: group.short_name,
              label: String(group.id),
              correct: count?.correct ?? 0,
              total: count?.total ?? 0,
            };
          })
        : BLOOM.map((label, i) => ({
            id: String(i + 1),
            number: i + 1,
            name: label,
            label,
            correct: shownLevels.find((l) => l.level === i + 1)?.correct ?? 0,
            total: shownLevels.find((l) => l.level === i + 1)?.total ?? 0,
          }));
  const chartKey = [
    perspective,
    activeSpecialty ? selected : "all",
    axes
      .map((axis) => `${axis.id}:${axis.name}:${axis.correct}/${axis.total}`)
      .join("|"),
  ].join(":");
  const matrix = learningMatrix(shownGroups, perspective);
  const activeRow =
    matrix.rows.find((r) => r.id === selectedRow) ??
    matrix.rows.find((r) => r.cells.some((c) => c.total > 0)) ??
    matrix.rows[0];
  const cell = matrix.rows
    .flatMap((row) => row.cells)
    .find((c) => c.id === selectedCell);
  const hasAssessment = axes.some((a) => a.total > 0);
  const unassessedCount = axes.filter((a) => a.total === 0).length;
  const perspectiveLabel =
    perspective === "specialty"
      ? activeSpecialty
        ? `vấn đề · ${activeSpecialty.short_name}`
        : "chuyên khoa"
      : "mức độ vận dụng";

  function changePerspective(next: AnalysisPerspective) {
    setPerspective(next);
    setSelected("all");
    setSelectedCell(null);
    setSelectedRow("");
    setSelectedAxisId(null);
  }

  return (
    <section
      className="panel stack learning-matrix mobile-analysis"
      aria-labelledby={headingId}
    >
      <div className="matrix-heading">
        <div>
          <h2 id={headingId}>Điểm mạnh &amp; cần ôn</h2>
          <p className="muted small">Dựa trên các đề đã nộp.</p>
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
      <div className="field matrix-filter">
        <label htmlFor={`${headingId}-specialty`}>
          {perspective === "specialty"
            ? "Đề mục chuyên khoa"
            : "Xem mức độ vận dụng theo chuyên khoa"}
        </label>
        <select
          id={`${headingId}-specialty`}
          value={activeSpecialty ? selected : "all"}
          onChange={(event) => {
            setSelected(event.target.value);
            setSelectedCell(null);
            setSelectedRow("");
            setSelectedAxisId(null);
          }}
        >
          <option value="all">Tất cả</option>
          {blueprint.groups.map((group) => (
            <option key={group.id} value={`g${group.id}`}>
              {group.id}. {group.short_name}
            </option>
          ))}
        </select>
      </div>
      <div className="analysis-section">
        <div className="analysis-view-heading">
          <h3>Tỷ lệ đúng theo {perspectiveLabel}</h3>
        </div>
        <div className="assessment-combined">
          <AssessmentRadar
            key={chartKey}
            axes={axes}
            label={`Biểu đồ tỷ lệ đúng theo ${perspectiveLabel}; các số trên trục tương ứng với chú giải bên dưới.`}
            selectedAxisId={selectedAxisId}
            onSelectAxis={(axisId) =>
              setSelectedAxisId((current) =>
                current === axisId ? null : axisId,
              )
            }
          />
          <ol
            className="assessment-legend"
            aria-label={`Chú giải theo ${perspectiveLabel}`}
          >
            {axes.map((axis) => {
              const pct = assessmentPercent(axis);
              return (
                <li key={axis.id}>
                  <button
                    type="button"
                    aria-pressed={selectedAxisId === axis.id}
                    onClick={() =>
                      setSelectedAxisId((current) =>
                        current === axis.id ? null : axis.id,
                      )
                    }
                  >
                    <span className="assessment-axis-number">
                      {axis.number}
                    </span>
                    <span className="assessment-legend-name">{axis.name}</span>
                    <span className="assessment-legend-result">
                      {pct === null
                        ? "Chưa có dữ liệu"
                        : `${pct}% · ${axis.correct}/${axis.total} câu đúng`}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
        {unassessedCount > 0 && (
          <p className="analysis-note">
            {unassessedCount} mục chưa có dữ liệu, chưa được tính là 0%.
          </p>
        )}
        {!hasAssessment && (
          <p className="muted small">
            Nộp đề thi thử để xem kết quả theo {perspectiveLabel}.{" "}
            <Link to="/thi-thu" className="link-btn">
              Làm đề thi thử
            </Link>
          </p>
        )}
      </div>
      {hasAssessment && (
        <details className="analysis-table-details">
          <summary>
            <span className="analysis-table-summary-copy">
              <strong>Chi tiết theo chuyên khoa và mức độ</strong>
              <small>
                Mở bảng kết quả, số câu đúng và phần chưa có dữ liệu
              </small>
            </span>
            <ChevronDown size={19} aria-hidden="true" />
          </summary>
          <div className="analysis-section">
            <div className="analysis-view-heading">
              <h3>So sánh kết quả</h3>
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
                              {perspective === "specialty"
                                ? c.bloom
                                : c.specialty}
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
                          Tỷ lệ đúng và số lượt câu theo chuyên khoa và sáu mức
                          độ từ ghi nhớ đến vận dụng. Dấu gạch ngang là chưa có
                          dữ liệu.
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
                  <div
                    className="matrix-detail"
                    role="status"
                    aria-live="polite"
                  >
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
                Chưa đủ kết quả để xem theo chuyên khoa và mức độ vận dụng. Khi
                bạn hoàn thành thêm bài, bảng sẽ hiển thị tại đây.
              </p>
            )}
          </div>
        </details>
      )}
    </section>
  );
}
