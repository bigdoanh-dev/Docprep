import {
  ChevronDown,
  ChevronRight,
  Download,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useActor } from "../../app/identity";
import { Sheet } from "../../components/Sheet";
import { LoadError, Loading } from "../../components/Status";
import { useFeedback } from "../../components/ui/Feedback";
import { staffApi, type AdminOverview } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { saveFile } from "../auth/Account";
import {
  Accuracy,
  Alerts,
  Bank,
  KpiTiles,
  Operations,
  Safety,
  Schools,
  WeeklyActive,
} from "./OverviewBlocks";

type TabKey = "overview" | "schools" | "learning" | "safety";

export function Dashboard() {
  const actor = useActor()!,
    notify = useFeedback(),
    loc = useLocation(),
    navigate = useNavigate();

  const [filters, setFilters] = useState({
    period: "",
    school: "",
    audience: "",
    region: "",
  });
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  // Tab routing synchronization
  const isSchoolsRoute = loc.pathname.endsWith("/co-so");
  const isLearningRoute = loc.pathname.endsWith("/ket-qua");
  const isSafetyRoute = loc.pathname.endsWith("/an-toan");
  const [activeTab, setActiveTab] = useState<TabKey>(
    isSchoolsRoute
      ? "schools"
      : isLearningRoute
        ? "learning"
        : isSafetyRoute
          ? "safety"
          : "overview",
  );

  // Keep state synced if route changes
  const currentTab: TabKey = isSchoolsRoute
    ? "schools"
    : isLearningRoute
      ? "learning"
      : isSafetyRoute
        ? "safety"
        : activeTab;

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab);
    if (tab === "schools") {
      navigate("/quan-ly/co-so");
    } else if (tab === "learning") {
      navigate("/quan-ly/ket-qua");
    } else if (tab === "safety") {
      navigate("/quan-ly/an-toan");
    } else {
      if (loc.pathname !== "/quan-ly") {
        navigate("/quan-ly");
      }
    }
  };

  const qs = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v),
  ).toString();

  const { data, error, reload } = useLoad(
    () => staffApi.get<AdminOverview>(`/admin/dashboard/overview?${qs}`),
    [qs],
  );

  const activeFiltersCount =
    (filters.period ? 1 : 0) +
    (filters.school ? 1 : 0) +
    (filters.audience ? 1 : 0) +
    (filters.region ? 1 : 0);

  const resetFilters = () => {
    setFilters({ period: "", school: "", audience: "", region: "" });
  };

  const download = async () => {
    setBusy(true);
    try {
      if (actor.mode === "demo") {
        saveFile(data, "bao-cao-tong-hop-minh-hoa.json");
        notify("Đã xuất dữ liệu tổng hợp minh họa dạng JSON.");
      } else {
        const { blob, fileName } = await staffApi.download(
          `/admin/dashboard/export?format=xlsx&${qs}`,
        );
        const url = URL.createObjectURL(blob),
          a = Object.assign(document.createElement("a"), {
            href: url,
            download: fileName ?? "bao-cao-tong-quan-toan-quoc.xlsx",
          });
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        notify("Đã tải báo cáo Excel thành công.");
      }
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };

  // Human-readable labels for currently active filter scope
  const activePeriodLabel =
    data?.filters.periods?.find((p: any) => p.value === filters.period)
      ?.label_vi || (data?.period ? `Kỳ ${data.period}` : "Kỳ gần nhất");
  const activeSchoolLabel =
    data?.filters.schools?.find((s: any) => s.value === filters.school)
      ?.label_vi || (filters.school ? filters.school : "Toàn quốc");

  return (
    <div className="dashboard-page">
      {/* 1. Compact App Bar */}
      <header className="dashboard-header">
        <div className="dashboard-title-group">
          <h1>
            {currentTab === "learning"
              ? "Kết quả 8 học phần"
              : currentTab === "safety"
                ? "An toàn AI & Tuân thủ"
                : currentTab === "schools"
                  ? "Cơ sở đào tạo"
                  : "Báo cáo tổng quan"}
          </h1>
        </div>
      </header>

      {/* 2. One Compact Filter Entry */}
      <div className="filter-single-bar">
        <button
          type="button"
          className={`filter-entry-btn ${activeFiltersCount > 0 ? "filtered" : ""}`}
          onClick={() => setFilterSheetOpen(true)}
          aria-label="Mở bộ lọc báo cáo"
        >
          <div className="filter-entry-left">
            <SlidersHorizontal size={13} />
            <span className="filter-entry-text">
              {activePeriodLabel} · {activeSchoolLabel}
              {filters.audience &&
                ` · ${filters.audience === "student" ? "Sinh viên" : "Tốt nghiệp"}`}
              {filters.region && ` · ${filters.region}`}
            </span>
          </div>
          <div className="filter-entry-right">
            {activeFiltersCount > 0 && (
              <span className="filter-entry-badge">{activeFiltersCount}</span>
            )}
            <ChevronDown size={14} className="filter-entry-arrow" />
          </div>
        </button>

        <button
          className="btn-export-excel"
          disabled={!data || busy}
          onClick={download}
          aria-label={
            actor.mode === "demo"
              ? "Xuất dữ liệu minh họa"
              : "Xuất báo cáo Excel"
          }
          title={
            actor.mode === "demo"
              ? "Tải dữ liệu minh họa (.json)"
              : "Tải báo cáo Excel (.xlsx)"
          }
        >
          <Download size={16} />
          <span>{busy ? "Đang xuất…" : "Xuất"}</span>
        </button>

        {activeFiltersCount > 0 && (
          <button
            type="button"
            className="filter-quick-reset"
            onClick={resetFilters}
            title="Xóa bộ lọc"
            aria-label="Xóa bộ lọc"
          >
            <RotateCcw size={13} />
          </button>
        )}
      </div>

      {/* 3. Compact Horizontal Tabs */}
      <nav className="dashboard-tab-bar" aria-label="Phân hệ báo cáo">
        <button
          type="button"
          className={`dash-tab ${currentTab === "overview" ? "active" : ""}`}
          aria-pressed={currentTab === "overview"}
          onClick={() => handleTabChange("overview")}
        >
          Tổng quan
        </button>
        <button
          type="button"
          className={`dash-tab ${currentTab === "schools" ? "active" : ""}`}
          aria-pressed={currentTab === "schools"}
          onClick={() => handleTabChange("schools")}
        >
          Cơ sở đào tạo
        </button>
        <button
          type="button"
          className={`dash-tab ${currentTab === "learning" ? "active" : ""}`}
          aria-pressed={currentTab === "learning"}
          onClick={() => handleTabChange("learning")}
        >
          8 Học phần
        </button>
        <button
          type="button"
          className={`dash-tab ${currentTab === "safety" ? "active" : ""}`}
          aria-pressed={currentTab === "safety"}
          onClick={() => handleTabChange("safety")}
        >
          An toàn AI
        </button>
      </nav>

      {/* Loading & Error States */}
      {error && <LoadError message={error} onRetry={reload} />}
      {!data && !error && <Loading />}

      {/* Suppression & Empty State */}
      {data && (data.suppressed || !data.kpis) ? (
        <div className="suppression-alert-card">
          <div className="suppression-icon-wrap">
            <ShieldCheck size={24} />
          </div>
          <h2>
            {data.suppressed
              ? "Số liệu được ẩn để bảo vệ nhóm nhỏ"
              : "Chưa có số liệu cho phạm vi này"}
          </h2>
          <p>
            {data.suppressed
              ? `Tổ hợp bộ lọc hiện tại có dưới ngưỡng ${data.suppression_min} học viên đã kích hoạt. Mọi dữ liệu tổng hợp được ẩn theo nguyên tắc bảo vệ quyền riêng tư.`
              : "Máy chủ chưa ghi nhận lượt hoạt động nào trong kỳ và phạm vi được chọn."}
          </p>
          <button className="btn primary" onClick={resetFilters}>
            <RotateCcw size={14} />
            Đặt lại tất cả bộ lọc
          </button>
        </div>
      ) : (
        data && (
          <div className="dashboard-tab-content">
            {/* Meta status info */}
            <div className="dashboard-status-meta">
              <span>
                Cập nhật{" "}
                {new Date(data.computed_at).toLocaleTimeString("vi-VN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}{" "}
                {new Date(data.computed_at).toLocaleDateString("vi-VN")}
              </span>
              {data.sample_data && actor.mode !== "demo" && (
                <span>Dữ liệu mẫu</span>
              )}
              <span>Ẩn nhóm dưới {data.suppression_min} học viên</span>
            </div>

            {/* TAB 1: Tổng quan (Short report overview) */}
            {currentTab === "overview" && (
              <div className="tab-pane-fade">
                {/* Key Metrics */}
                <KpiTiles kpis={data.kpis!} period={data.period} />

                {/* Brief Alerts (if any) */}
                <Alerts alerts={data.alerts} />

                {/* Activity Snapshot */}
                {data.weekly_active && (
                  <WeeklyActive
                    weekly={data.weekly_active}
                    scope={activeSchoolLabel}
                  />
                )}

                {/* Drill-down shortcuts */}
                <div className="drilldown-card">
                  <span className="drilldown-header-title">
                    Báo cáo chi tiết
                  </span>
                  <div className="drilldown-list">
                    <button
                      type="button"
                      className="drilldown-row"
                      onClick={() => handleTabChange("schools")}
                    >
                      <div className="drilldown-info">
                        <strong>Cơ sở đào tạo</strong>
                        <span>Số liệu và tỷ lệ kích hoạt từng trường</span>
                      </div>
                      <ChevronRight size={16} className="drilldown-arrow" />
                    </button>
                    <button
                      type="button"
                      className="drilldown-row"
                      onClick={() => handleTabChange("learning")}
                    >
                      <div className="drilldown-info">
                        <strong>Kết quả 8 học phần & Ngân hàng đề</strong>
                        <span>
                          Tỷ lệ đúng theo môn học và tiến độ thẩm định
                        </span>
                      </div>
                      <ChevronRight size={16} className="drilldown-arrow" />
                    </button>
                    <button
                      type="button"
                      className="drilldown-row"
                      onClick={() => handleTabChange("safety")}
                    >
                      <div className="drilldown-info">
                        <strong>An toàn câu trả lời AI & Vận hành</strong>
                        <span>Tỷ lệ trích dẫn, từ chối và độ trễ</span>
                      </div>
                      <ChevronRight size={16} className="drilldown-arrow" />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: Cơ sở đào tạo */}
            {currentTab === "schools" && (
              <div className="tab-pane-fade">
                {data.schools && (
                  <Schools
                    schools={data.schools}
                    minimum={data.suppression_min}
                  />
                )}
              </div>
            )}

            {/* TAB 3: 8 Học phần & Ngân hàng câu hỏi */}
            {currentTab === "learning" && (
              <div className="tab-pane-fade">
                {data.accuracy_by_module && (
                  <Accuracy
                    accuracy={data.accuracy_by_module}
                    period={data.period}
                  />
                )}
                {data.question_bank && (
                  <Bank bank={data.question_bank} period={data.period} />
                )}
              </div>
            )}

            {/* TAB 4: An toàn AI & Vận hành */}
            {currentTab === "safety" && (
              <div className="tab-pane-fade">
                {data.ai_safety && (
                  <Safety ai={data.ai_safety} period={data.period} />
                )}
                {data.compliance && <Operations compliance={data.compliance} />}
              </div>
            )}
          </div>
        )
      )}

      {/* Filter Bottom Sheet */}
      <Sheet
        open={filterSheetOpen}
        onClose={() => setFilterSheetOpen(false)}
        title="Bộ lọc báo cáo tổng hợp"
      >
        <div className="filter-sheet-body">
          <p className="filter-sheet-subtitle">
            Dữ liệu tổng hợp sẽ được tính toán trực tiếp từ máy chủ theo phạm vi
            chọn.
          </p>

          <div className="filter-fields-stack">
            <label className="filter-field-label">
              <span>Kỳ báo cáo (Tháng)</span>
              <select
                className="filter-select"
                value={filters.period}
                onChange={(e) =>
                  setFilters({ ...filters, period: e.target.value })
                }
              >
                <option value="">
                  Kỳ mặc định ({data?.period || "gần nhất"})
                </option>
                {data?.filters.periods?.map((p: any) => (
                  <option key={p.value} value={p.value}>
                    {p.label_vi}
                  </option>
                ))}
              </select>
            </label>

            <label className="filter-field-label">
              <span>Cơ sở đào tạo</span>
              <select
                className="filter-select"
                value={filters.school}
                onChange={(e) =>
                  setFilters({ ...filters, school: e.target.value })
                }
              >
                <option value="">Tất cả cơ sở đào tạo</option>
                {data?.filters.schools?.map((s: any) => (
                  <option key={s.value} value={s.value}>
                    {s.label_vi}
                  </option>
                ))}
                {actor.mode === "demo" && (
                  <option value="CSDT-F">
                    CSĐT F (Kiểm thử ẩn nhóm &lt; 10)
                  </option>
                )}
              </select>
            </label>

            <label className="filter-field-label">
              <span>Đối tượng người học</span>
              <select
                className="filter-select"
                value={filters.audience}
                onChange={(e) =>
                  setFilters({ ...filters, audience: e.target.value })
                }
              >
                <option value="">Tất cả đối tượng</option>
                {data?.filters.audiences?.map((a: any) => (
                  <option key={a.value} value={a.value}>
                    {a.label_vi}
                  </option>
                ))}
              </select>
            </label>

            <label className="filter-field-label">
              <span>Vùng địa lý</span>
              <select
                className="filter-select"
                value={filters.region}
                onChange={(e) =>
                  setFilters({ ...filters, region: e.target.value })
                }
              >
                <option value="">Tất cả các vùng</option>
                {data?.filters.regions?.map((r: any) => (
                  <option key={r.value} value={r.value}>
                    {r.label_vi}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="filter-sheet-actions">
            {activeFiltersCount > 0 && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={resetFilters}
              >
                Đặt lại
              </button>
            )}
            <button
              type="button"
              className="btn primary btn-apply"
              onClick={() => setFilterSheetOpen(false)}
            >
              Áp dụng bộ lọc
            </button>
          </div>
        </div>
      </Sheet>
    </div>
  );
}
