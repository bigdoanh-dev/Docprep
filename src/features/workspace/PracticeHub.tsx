import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Clock,
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
    <div className="screen stack">
      <header className="page-heading">
        <h1>Ôn tập theo cách của bạn</h1>
        <p>
          Chọn chuyên khoa hoặc trộn câu hỏi từ các nhóm có trong ngân hàng.
        </p>
      </header>
      <div className="practice-intro-card">
        <div className="practice-intro-main">
          <span className="practice-intro-icon" aria-hidden="true">
            <Stethoscope size={22} />
          </span>
          <div className="practice-intro-text">
            <div className="practice-intro-badge-row">
              <span className="practice-role-badge">Chương trình hiện tại</span>
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
        <h2>Bắt đầu một lượt ôn</h2>
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
            <strong>Ôn tập ngẫu nhiên</strong>
            <span>Trộn câu hỏi từ các nhóm đang có câu trong kho.</span>
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
              <span className="label-hint-badge">
                <Clock size={13} />
                {count === 5 && "Dự kiến: ~8 phút · Ôn nhanh"}
                {count === 10 && "Dự kiến: ~18 phút · Khuyên dùng"}
                {count === 20 && "Dự kiến: ~35 phút · Chuyên sâu"}
              </span>
            </div>

            <div
              className="practice-count-cards"
              role="radiogroup"
              aria-label="Số câu hỏi trong phiên"
            >
              {[
                {
                  val: 5,
                  label: "5 câu",
                  sub: "Khởi động nhanh",
                  time: "~8 phút",
                  badge: null,
                },
                {
                  val: 10,
                  label: "10 câu",
                  sub: "Phiên tiêu chuẩn",
                  time: "~18 phút",
                  badge: "Khuyên dùng",
                },
                {
                  val: 20,
                  label: "20 câu",
                  sub: "Luyện chuyên sâu",
                  time: "~35 phút",
                  badge: "Thử thách",
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
          Không tính giờ. Nhận giải thích và nguồn học liệu sau từng câu.
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
        <button
          className="btn primary"
          disabled={busy || actor.mode !== "demo" || !data}
          onClick={start}
        >
          {busy ? "Đang chuẩn bị…" : "Bắt đầu ôn tập"}
          <ArrowRight size={18} />
        </button>
      </section>
    </div>
  );
}
