import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Layers,
  Shuffle,
  SlidersHorizontal,
  Stethoscope,
} from "lucide-react";
import { useActor } from "../../app/identity";
import { api, type Listed, type Module, type Me } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { LoadError } from "../../components/Status";
import { learnerAudienceNames } from "../../lib/learnerProfile";
export function PracticeHub() {
  const actor = useActor()!,
    navigate = useNavigate();
  const { data, error, reload } = useLoad(async () => {
    const [modules, me] = await Promise.all([
      api.get<Listed<Module>>("/modules"),
      api.get<Me>("/me"),
    ]);
    return { modules: modules.items, me };
  }, []);
  const [mode, setMode] = useState("specialty"),
    [module, setModule] = useState("g1"),
    [count, setCount] = useState(10),
    [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState("");
  const start = async () => {
    setBusy(true);
    setActionError("");
    try {
      const set = await api.post<{ id: number }>("/practice-sets", {
        module_id: mode === "random" ? null : module,
        count,
        random: mode === "random",
      });
      navigate(`/luyen-tap/bo-cau/${set.id}`);
    } catch (e) {
      setActionError((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <div className="screen stack practice-page">
      <div className="practice-intro-card">
        <div className="practice-intro-main">
          <span className="practice-intro-icon" aria-hidden="true">
            <Stethoscope size={22} />
          </span>
          <div className="practice-intro-text">
            <div className="practice-intro-badge-row">
              <span className="practice-role-badge">Trọng tâm ôn tập</span>
              <h2>Y học dự phòng</h2>
            </div>
            <p>
              {data ? `${learnerAudienceNames[data.me.audience]} · ` : ""}Ôn tập
              theo nhóm năng lực.
            </p>
          </div>
        </div>
        <Link className="practice-role-link" to="/chon-hoc-phan?doi=1">
          Đổi trọng tâm
        </Link>
      </div>
      {error && <LoadError message={error} onRetry={reload} />}
      <section className="panel stack">
        <h2>Thiết lập lượt ôn</h2>
        <button
          className="btn primary practice-start"
          disabled={busy || actor.mode !== "demo" || !data}
          onClick={start}
        >
          {busy ? "Đang chuẩn bị…" : "Bắt đầu ôn tập"}
          <ArrowRight size={18} />
        </button>
        <div className="practice-modes">
          <button
            className={`choice-panel ${mode === "specialty" ? "selected" : ""}`}
            aria-pressed={mode === "specialty"}
            onClick={() => setMode("specialty")}
          >
            <span className="choice-panel-icon" aria-hidden="true">
              <BookOpen size={20} />
            </span>
            <strong>Ôn theo chuyên khoa</strong>
            <span>Tập trung một nhóm năng lực bạn muốn củng cố.</span>
          </button>
          <button
            className={`choice-panel ${mode === "random" ? "selected" : ""}`}
            aria-pressed={mode === "random"}
            onClick={() => setMode("random")}
          >
            <span className="choice-panel-icon" aria-hidden="true">
              <Shuffle size={20} />
            </span>
            <strong>Ôn tập tổng hợp</strong>
            <span>Củng cố kiến thức qua câu hỏi từ nhiều nhóm năng lực.</span>
          </button>
        </div>
        <div className="practice-config-section">
          {mode === "specialty" && (
            <div className="practice-config-block">
              <label
                className="practice-config-label"
                htmlFor="practice-module-select"
              >
                <span className="label-title-wrap">
                  <Layers size={16} className="label-icon" />
                  <strong>Chuyên khoa / Nhóm năng lực</strong>
                </span>
                <span className="label-hint">
                  Chọn học phần cần củng cố kiến thức
                </span>
              </label>
              <div className="practice-select-wrapper">
                <select
                  id="practice-module-select"
                  className="practice-custom-select"
                  value={module}
                  onChange={(e) => setModule(e.target.value)}
                >
                  {data?.modules.map((m) => (
                    <option key={m.id} value={m.id} disabled={m.coming_soon}>
                      {m.short_name}
                      {m.coming_soon ? " — Đang xây dựng" : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <div className="practice-config-block">
            <div className="practice-config-label">
              <span className="label-title-wrap">
                <SlidersHorizontal size={16} className="label-icon" />
                <strong>Số câu hỏi trong phiên</strong>
              </span>
            </div>

            <div
              className="practice-count-cards"
              role="radiogroup"
              aria-label="Số câu hỏi trong phiên"
            >
              {[
                {
                  val: 10,
                  label: "10 câu",
                  sub: "Ôn nhanh",
                  time: "",
                  badge: "Khuyên dùng",
                },
                {
                  val: 20,
                  label: "20 câu",
                  sub: "Ôn nhanh",
                  time: "",
                  badge: null,
                },
                {
                  val: 30,
                  label: "30 câu",
                  sub: "Củng cố",
                  time: "",
                  badge: null,
                },
                {
                  val: 60,
                  label: "60 câu",
                  sub: "Ôn mở rộng",
                  time: "",
                  badge: null,
                },
              ].map((opt) => {
                const isSelected = count === opt.val;
                return (
                  <button
                    key={opt.val}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    className={`practice-count-card ${isSelected ? "selected" : ""}`}
                    onClick={() => setCount(opt.val)}
                  >
                    <div className="count-card-header">
                      <div className="count-radio-indicator" aria-hidden="true">
                        <span className="radio-inner" />
                      </div>
                      <span className="count-card-number">{opt.label}</span>
                      {opt.badge && (
                        <span
                          className={`count-card-badge ${opt.val === 10 ? "recommended" : ""}`}
                        >
                          {opt.badge}
                        </span>
                      )}
                    </div>
                    <div className="count-card-meta">
                      <span className="count-card-sub">{opt.sub}</span>
                      <span className="count-card-time">{opt.time}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        <p className="muted small">
          Không tính giờ. Nhận giải thích và nguồn học liệu sau từng câu. Kho
          minh họa có thể có ít câu hơn lựa chọn; phiên chỉ dùng các câu sẵn có,
          không lặp câu.
        </p>
        {actor.mode === "live" && (
          <p className="notice">
            Tạo bộ ôn tùy chọn đang chờ tích hợp máy chủ. Bạn có thể tiếp tục
            học phần hoặc phiên học hôm nay.
          </p>
        )}
        {actionError && (
          <p className="warn" role="alert">
            {actionError}
          </p>
        )}
      </section>
    </div>
  );
}
