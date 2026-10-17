import { AlertTriangle, ChevronDown, Info, ShieldCheck } from "lucide-react";
import {
  CHART,
  DASH,
  change,
  chart,
  chartLabel,
  count,
  days,
  delta,
  periodLabel,
  score,
  seconds,
  sharePct,
  type AdminOverview,
  type AiSafety,
  type Compliance,
  type Kpis,
  type QuestionBank,
} from "../../lib/dashboard";

type Present<K extends keyof AdminOverview> = NonNullable<AdminOverview[K]>;
const month = (period: string) => periodLabel(period).toLowerCase(); // "tháng 9/2026"
const width = (share: number | null) => ({
  width: `${Math.round(Math.min(1, Math.max(0, share ?? 0)) * 100)}%`,
});

export function KpiTiles({ kpis, period }: { kpis: Kpis; period: string }) {
  const previous =
    Number(period.slice(5, 7)) === 1 ? 12 : Number(period.slice(5, 7)) - 1;
  const moved = delta(kpis.active_learners, kpis.active_learners_previous);
  const ofIssued = (n: number) =>
    kpis.accounts_issued > 0 ? sharePct(n / kpis.accounts_issued) : DASH;

  // 3 compact key metrics for Overview (Mock stats moved to Learning, AI citations moved to Safety)
  const tiles = [
    {
      id: "active",
      label: "Học viên hoạt động",
      subLabel: "trong tháng",
      value: count(kpis.active_learners),
      badge: moved,
      badgePositive: moved && !moved.startsWith("−"),
      note: `${ofIssued(kpis.active_learners)} tài khoản đã cấp${moved ? ` · so với T${previous}` : ""}`,
    },
    {
      id: "activated",
      label: "Tài khoản đã kích hoạt",
      subLabel: "tỷ lệ kích hoạt",
      value: count(kpis.accounts_activated),
      badge: ofIssued(kpis.accounts_activated),
      badgePositive:
        kpis.accounts_issued > 0 &&
        kpis.accounts_activated / kpis.accounts_issued >= 0.6,
      note: `Đạt ${ofIssued(kpis.accounts_activated)} trên tổng số ${count(kpis.accounts_issued)} tài khoản`,
    },
    {
      id: "practice",
      label: "Câu luyện tập đã làm",
      subLabel: "tổng lượt trả lời",
      value: count(kpis.practice_items),
      note:
        kpis.active_learners > 0
          ? `Trung bình ${count(kpis.practice_items / kpis.active_learners)} câu/học viên`
          : "Chưa ghi nhận học viên hoạt động",
    },
  ];

  return (
    <section aria-label="Chỉ số chính" className="kpis-container">
      <div className="kpis-grid three-kpis">
        {tiles.map((tile) => (
          <div className={`kpi-card kpi-${tile.id}`} key={tile.id}>
            <div className="kpi-card-header">
              <div>
                <span className="kpi-card-label">{tile.label}</span>
                {tile.subLabel && (
                  <span className="kpi-card-sublabel">{tile.subLabel}</span>
                )}
              </div>
              {tile.badge && (
                <span
                  className={`kpi-trend-badge ${tile.badgePositive ? "positive" : "neutral"}`}
                >
                  {tile.badge}
                </span>
              )}
            </div>
            <div className="kpi-card-value">{tile.value}</div>
            <p className="kpi-card-note">{tile.note}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function WeeklyActive({
  weekly,
  scope,
}: {
  weekly: Present<"weekly_active">;
  scope: string;
}) {
  const g = chart(weekly.weeks);
  const font = {
    fontFamily: "Be Vietnam Pro, sans-serif",
    fill: "#64748B",
    fontSize: 10,
  };

  return (
    <section id="reach" aria-labelledby="wau-title" className="admin-card">
      <div className="admin-card-head">
        <div>
          <h2 id="wau-title">Học viên hoạt động mỗi tuần</h2>
          <p className="admin-sub">12 tuần kết thúc theo kỳ · {scope}</p>
        </div>
      </div>

      <div className="weekly-chart-wrapper">
        <svg
          viewBox={`0 0 ${CHART.width} ${CHART.height}`}
          className="weekly-chart-svg"
          role="img"
          aria-label={chartLabel(weekly.weeks)}
        >
          {g.ticks.map((tick) => (
            <g key={tick.y}>
              <path
                d={`M${CHART.gridLeft} ${tick.y}H${CHART.gridRight}`}
                stroke="#E2E8F0"
                strokeWidth="1"
                strokeDasharray="2,3"
              />
              <text
                x={CHART.gridLeft - 8}
                y={tick.y + 4}
                textAnchor="end"
                {...font}
              >
                {tick.label}
              </text>
            </g>
          ))}
          {g.area && <path d={g.area} fill="#0D9488" fillOpacity="0.12" />}
          {g.line && (
            <polyline
              points={g.line}
              fill="none"
              stroke="#0D9488"
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}
          {g.end && (
            <>
              <circle
                cx={g.end.x}
                cy={g.end.y}
                r="5"
                fill="#0D9488"
                stroke="#FFFFFF"
                strokeWidth="2"
              />
              <text
                x={g.end.x - 8}
                y={g.end.y - 12}
                textAnchor="end"
                fontSize="12"
                fontWeight="700"
                fill="#0F172A"
                fontFamily={font.fontFamily}
              >
                {g.end.label}
              </text>
            </>
          )}
          {g.labels
            .filter(
              (_, index) => index % 3 === 0 || index === g.labels.length - 1,
            )
            .map((label) => (
              <text
                key={label.x}
                x={label.x}
                y="214"
                textAnchor="middle"
                {...font}
              >
                {label.text}
              </text>
            ))}
        </svg>
      </div>

      <div className="retention-grid">
        <div className="retention-heading">
          <span className="retention-title">Tỷ lệ quay lại</span>
          <span className="retention-sub">Tính từ lần đầu hoạt động</span>
        </div>
        <div className="retention-cards">
          {weekly.retention.map((item) => (
            <div className="retention-card" key={item.weeks}>
              <span className="ret-label">Sau {item.weeks} tuần</span>
              <strong className="ret-value">{sharePct(item.share)}</strong>
              <span className="ret-note">{count(item.learners)} học viên</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Alerts({ alerts }: { alerts: AdminOverview["alerts"] }) {
  if (alerts.length === 0) return null;

  return (
    <details className="alert-disclosure">
      <summary className="alert-summary">
        <div className="alert-summary-left">
          <AlertTriangle size={14} className="alert-icon-warn" />
          <span className="alert-summary-title">
            {alerts.length} cảnh báo cần xem
          </span>
        </div>
        <ChevronDown size={14} className="alert-summary-arrow" />
      </summary>
      <div className="alert-disclosure-list">
        {alerts.map((alert, index) => (
          <div className="alert-item" key={index}>
            <strong>{alert.title_vi}</strong>
            <p>{alert.detail_vi}</p>
          </div>
        ))}
      </div>
    </details>
  );
}

export function Accuracy({
  accuracy,
  period,
  kpis,
}: {
  accuracy: Present<"accuracy_by_module">;
  period: string;
  kpis?: Kpis;
}) {
  const median = kpis?.mock_median;

  return (
    <section id="learning" aria-labelledby="learn-title" className="admin-card">
      <div className="admin-card-head">
        <div>
          <h2 id="learn-title">Kết quả theo 8 học phần</h2>
          <p className="admin-sub">
            Thi thử {month(period)} · {count(accuracy.learners)} học viên có đồng thuận nghiên cứu
          </p>
        </div>
      </div>

      {kpis && (
        <div className="mock-stat-tile">
          <div className="mock-stat-main">
            <span className="mock-stat-label">Lượt thi thử toàn quốc</span>
            <strong className="mock-stat-val">{count(kpis.mock_attempts)} lượt</strong>
          </div>
          <span className="mock-stat-note">
            {median
              ? `Trung vị ${score(median)} đúng · ${count(median.learners)} học viên đồng thuận`
              : "Trung vị ẩn: chưa đủ học viên đồng thuận"}
          </span>
        </div>
      )}

      <div className="module-bars-list">
        {accuracy.items.map((item) => (
          <div className="module-bar-card" key={item.module_id}>
            <div className="module-bar-meta">
              <span className="module-name">{item.short_name}</span>
              <strong className={`module-pct ${item.low ? "low-text" : ""}`}>
                {sharePct(item.share)}
              </strong>
            </div>
            <div className="module-progress-track">
              <div
                className={`module-progress-fill ${item.low ? "fill-low" : "fill-primary"}`}
                style={width(item.share)}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="module-legend-box">
        <span className="legend-indicator">
          <span className="dot dot-low" /> Dưới 60% câu đúng (cần tăng cường ôn tập)
        </span>
        <span className="legend-indicator">
          <span className="dot dot-normal" /> Đạt yêu cầu
        </span>
      </div>

      <p className="admin-footnote">
        <Info size={13} />
        Chỉ tính kết quả thi thử của học viên có đồng thuận nghiên cứu hợp lệ tại thời điểm kết thúc kỳ. Tuyệt đối không dự đoán điểm thi hay xếp loại đỗ/trượt.
      </p>
    </section>
  );
}

const BANK_PARTS: {
  key: "approved" | "in_review" | "draft" | "rejected";
  label: string;
  colour: string;
}[] = [
  { key: "approved", label: "Đã duyệt", colour: "#0D9488" },
  { key: "in_review", label: "Đang duyệt", colour: "#38BDF8" },
  { key: "draft", label: "Nháp", colour: "#94A3B8" },
  { key: "rejected", label: "Loại", colour: "#CBD5E1" },
];

export function Bank({ bank, period }: { bank: QuestionBank; period: string }) {
  const slow =
    bank.round2_median_days !== null &&
    bank.round2_median_days > bank.round2_target_days;

  return (
    <section id="content" aria-labelledby="bank-title" className="admin-card">
      <div className="admin-card-head">
        <div>
          <h2 id="bank-title">Ngân hàng câu hỏi</h2>
          <p className="admin-sub">
            Toàn bộ ngân hàng (không phụ thuộc bộ lọc trường, vùng hay đối tượng)
          </p>
        </div>
      </div>

      <div className="bank-hero-stat">
        <div className="bank-approved-pill">
          <span className="bank-approved-val">{count(bank.approved)}</span>
          <span className="bank-approved-lbl">câu đã duyệt qua 2 vòng độc lập</span>
        </div>
        <div className="bank-split-bar" aria-hidden="true">
          {BANK_PARTS.map((part) => (
            <span
              key={part.key}
              style={{ flex: `${bank[part.key] || 0.1} 1 0`, background: part.colour }}
            />
          ))}
        </div>
        <div className="bank-legend-row">
          {BANK_PARTS.map((part) => (
            <div className="bank-legend-chip" key={part.key}>
              <i style={{ background: part.colour }} />
              <span>{part.label}: <strong>{count(bank[part.key])}</strong></span>
            </div>
          ))}
        </div>
      </div>

      <div className="metric-rows-stack">
        <div className="metric-data-row">
          <span className="metric-name">Vấn đề cốt lõi có ≥ {bank.min_approved_per_issue} câu duyệt</span>
          <strong className="metric-num">
            {bank.issues_covered} / {bank.issues_total}
          </strong>
        </div>
        <div className="metric-data-row">
          <span className="metric-name">Thời gian duyệt Vòng 1 (trung vị)</span>
          <strong className="metric-num">
            {bank.round1_median_days === null ? DASH : `${days(bank.round1_median_days)} ngày`}
          </strong>
        </div>
        <div className="metric-data-row">
          <span className="metric-name">Thời gian duyệt Vòng 2 (trung vị)</span>
          <strong className={`metric-num ${slow ? "text-warn" : ""}`}>
            {bank.round2_median_days === null ? DASH : `${days(bank.round2_median_days)} ngày`}
            <span className="metric-sub-tag">mục tiêu {bank.round2_target_days} ngày</span>
          </strong>
        </div>
        <div className="metric-data-row">
          <span className="metric-name">Hai vòng thẩm định cùng kết luận</span>
          <strong className="metric-num">{sharePct(bank.rounds_agree_share)}</strong>
        </div>
        <div className="metric-data-row">
          <span className="metric-name">Báo lỗi từ học viên ({month(period)})</span>
          <strong className="metric-num">
            {count(bank.reports_received)} nhận · đã xử lý {count(bank.reports_resolved)}
          </strong>
        </div>
      </div>
    </section>
  );
}

export function Safety({ ai, period }: { ai: AiSafety; period: string }) {
  const versions = [
    ai.model_versions.length > 0 && `Model: ${ai.model_versions.join(", ")}`,
    ai.corpus_versions.length > 0 && `Corpus: ${ai.corpus_versions.join(", ")}`,
  ].filter(Boolean);

  return (
    <section id="ai" aria-labelledby="ai-title" className="admin-card">
      <div className="admin-card-head">
        <div>
          <h2 id="ai-title">An toàn câu trả lời AI</h2>
          <p className="admin-sub">
            {[
              `${count(ai.answers)} lượt trả lời ${month(period)}`,
              ...versions,
            ].join(" · ")}
          </p>
        </div>
      </div>

      <div className="safety-target-box">
        <div className="safety-target-header">
          <span className="safety-target-label">Nhận định có trích dẫn đến cấp trang</span>
          <strong className="safety-target-val">{sharePct(ai.cited_claims_share, 1)}</strong>
        </div>
        <div className="safety-target-bar">
          <div className="bar-track">
            <div className="bar-fill" style={width(ai.cited_claims_share)} />
          </div>
          <span className="safety-target-note">
            Mục tiêu chuẩn ≥ {sharePct(ai.cited_claims_target)} (NFR-07)
          </span>
        </div>
      </div>

      <div className="metric-rows-stack">
        <div className="metric-data-row">
          <span className="metric-name">Từ chối vì thiếu bằng chứng học liệu</span>
          <strong className="metric-num">{sharePct(ai.insufficient_share, 1)}</strong>
        </div>
        <div className="metric-data-row">
          <span className="metric-name">Từ chối tư vấn ca bệnh cụ thể (Pre-gate)</span>
          <strong className="metric-num">{sharePct(ai.declined_share, 1)}</strong>
        </div>
        <div className="metric-data-row">
          <span className="metric-name">Bị hậu kiểm trích dẫn loại bỏ nhận định</span>
          <strong className="metric-num">{sharePct(ai.flagged_share, 1)}</strong>
        </div>
        <div className="metric-data-row">
          <span className="metric-name">Báo lỗi trên 1.000 câu trả lời</span>
          <strong className="metric-num">{days(ai.reports_per_1000)}</strong>
        </div>
      </div>
    </section>
  );
}

export function Schools({
  schools,
  minimum,
}: {
  schools: Present<"schools">;
  minimum: number;
}) {
  return (
    <section aria-labelledby="inst-title" className="admin-card schools-card">
      <div className="admin-card-head">
        <div>
          <h2 id="inst-title">Theo cơ sở đào tạo</h2>
          <p className="admin-sub">
            Chỉ số thi thử thực tế theo cơ sở · Ngưỡng ẩn {minimum} học viên
          </p>
        </div>
      </div>

      {schools.rows.length === 0 ? (
        <div className="empty-sub-card">
          <p>Không có cơ sở đào tạo nào đạt ngưỡng {minimum} học viên trong phạm vi đang chọn.</p>
        </div>
      ) : (
        <div className="schools-cards-list">
          {schools.rows.map((row) => {
            const rate =
              row.accounts_issued > 0
                ? row.accounts_activated / row.accounts_issued
                : null;
            return (
              <div className="school-item-card" key={row.code}>
                <div className="school-card-top">
                  <div className="school-title-group">
                    <span className="school-code-tag">{row.code}</span>
                    <h3 className="school-name-text">{row.name}</h3>
                  </div>
                  <div className="school-pill-group">
                    {row.region && <span className="school-region-pill">{row.region}</span>}
                    {row.activation_low && (
                      <span className="school-alert-pill" title="Tỷ lệ kích hoạt dưới 60%">
                        <AlertTriangle size={12} />
                        &lt;60% kích hoạt
                      </span>
                    )}
                  </div>
                </div>

                <div className="school-stats-grid">
                  <div className="school-stat-block full">
                    <div className="stat-label-row">
                      <span className="stat-lbl">Tài khoản cấp & kích hoạt</span>
                      <span className={`stat-pct ${row.activation_low ? "text-warn" : ""}`}>
                        {count(row.accounts_activated)} / {count(row.accounts_issued)} ({sharePct(rate)})
                      </span>
                    </div>
                    <div className="stat-progress-track">
                      <div
                        className={`stat-progress-fill ${row.activation_low ? "fill-warn" : "fill-primary"}`}
                        style={width(rate)}
                      />
                    </div>
                  </div>

                  <div className="school-stat-block">
                    <span className="stat-lbl">Hoạt động TB</span>
                    <strong className="stat-val">{days(row.weekly_active)} <span className="stat-unit">hv/tuần</span></strong>
                  </div>

                  <div className="school-stat-block">
                    <span className="stat-lbl">Lượt thi thử</span>
                    <strong className="stat-val">{count(row.mock_attempts)} <span className="stat-unit">lượt</span></strong>
                  </div>

                  <div className="school-stat-block">
                    <span className="stat-lbl">Trung vị điểm</span>
                    <strong className="stat-val">{score(row.mock_median)}</strong>
                  </div>

                  <div className="school-stat-block">
                    <span className="stat-lbl">Mức cải thiện</span>
                    <strong className="stat-val stat-change">{change(row.first_to_latest)}</strong>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {schools.hidden.length > 0 && (
        <div className="hidden-schools-banner">
          <div className="hidden-banner-header">
            <ShieldCheck size={16} />
            <strong>Cơ sở đào tạo được ẩn số liệu riêng ({schools.hidden.length})</strong>
          </div>
          <div className="hidden-schools-chips">
            {schools.hidden.map((school) => (
              <span className="hidden-school-pill" key={school.name}>
                {school.name} ({[school.region, `${school.learners} học viên`].filter(Boolean).join(" · ")})
              </span>
            ))}
          </div>
          <p className="hidden-banner-note">
            Các cơ sở có dưới {minimum} học viên được bảo vệ quyền riêng tư theo quy tắc bảo vệ dữ liệu. Số liệu của cơ sở vẫn được cộng vào tổng số toàn quốc.
          </p>
        </div>
      )}

      <p className="admin-footnote">
        <Info size={13} />
        Ký hiệu “–”: Điểm thi thử được ẩn vì cơ sở có dưới {minimum} học viên đồng ý dùng dữ liệu nghiên cứu. Tuyệt đối không dự đoán điểm thi hay xếp loại đỗ/trượt.
      </p>
    </section>
  );
}

export function Operations({ compliance }: { compliance: Compliance }) {
  const target = seconds(compliance.chat_target_ms);
  const met =
    compliance.chat_p95_ms !== null &&
    compliance.chat_p95_ms < compliance.chat_target_ms;

  return (
    <section id="ops" aria-labelledby="ops-title" className="admin-card">
      <div className="admin-card-head">
        <div>
          <h2 id="ops-title">Vận hành và tuân thủ</h2>
          <p className="admin-sub">Độ trễ hệ thống và bảo vệ dữ liệu cá nhân</p>
        </div>
      </div>

      <div className="metric-rows-stack">
        <div className="metric-data-row">
          <span className="metric-name">Độ trễ một lượt hỏi đáp (P95)</span>
          <strong className="metric-num">
            {seconds(compliance.chat_p95_ms)}
            {compliance.chat_p95_ms !== null && (
              <span className={`ops-status-tag ${met ? "tag-pass" : "tag-fail"}`}>
                {met ? "Đạt" : "Chưa đạt"} &lt; {target}
              </span>
            )}
          </strong>
        </div>

        <div className="metric-data-row">
          <span className="metric-name">Đồng ý dùng dữ liệu cho nghiên cứu</span>
          <strong className="metric-num">
            {count(compliance.research_consent_learners)} học viên · {sharePct(compliance.research_consent_share)}
          </strong>
        </div>

        <div className="metric-data-row">
          <span className="metric-name">Rút đồng ý / Yêu cầu xóa dữ liệu</span>
          <strong className="metric-num">
            {count(compliance.consent_withdrawals)} / {count(compliance.deletion_requests)}
            {compliance.deletion_median_days !== null &&
              ` · trung vị ${days(compliance.deletion_median_days)} ngày`}
          </strong>
        </div>
      </div>

      <div className="ops-infra-notice">
        <Info size={14} />
        <span>
          Thời gian hoạt động (uptime), nhật ký sự cố, sao lưu tự động và chỉ tiêu số hóa đang ở giai đoạn chuẩn bị hạ tầng Cloud NHIC, chưa có nguồn đo thời gian thực trên R1.0.
        </span>
      </div>
    </section>
  );
}

// Backward compatibility export if needed by legacy views (returns null, no fictitious figures rendered)
export function Cost() {
  return null;
}
