import {
  ArrowRight,
  BarChart3,
  Eye,
  EyeOff,
  GraduationCap,
  Settings2,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { roleHome, setActor, useActor, type Role } from "../../app/identity";
import { publicPost, type TokenPair } from "../../lib/api";
import { session, staffSession } from "../../lib/client";
import { clearWorkspace } from "../../lib/learnerWorkspace";
import { resetDemo } from "../../lib/demo/store";

const demoProfiles = [
  {
    role: "learner",
    id: "demo-learner",
    name: "Nguyễn Thu Hà",
    label: "Người học",
    Icon: GraduationCap,
  },
  {
    role: "ministry_viewer",
    id: "demo-ministry",
    name: "Cán bộ quản lý",
    label: "Cán bộ xem báo cáo",
    Icon: BarChart3,
  },
  {
    role: "admin",
    id: "demo-admin",
    name: "Quản trị viên",
    label: "Quản trị viên",
    Icon: Settings2,
  },
] as const;

const mobileRoles: Role[] = ["learner", "admin", "ministry_viewer"];

function safeNextPath(next: string | null): string | null {
  if (
    !next ||
    !next.startsWith("/") ||
    next.startsWith("//") ||
    next === "/dang-nhap"
  )
    return null;
  const target = new URL(next, window.location.origin);
  return target.origin === window.location.origin
    ? `${target.pathname}${target.search}${target.hash}`
    : null;
}

export function Login({ onDemoStart }: { onDemoStart: () => void }) {
  const actor = useActor();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [mode, setMode] = useState<"learner" | "staff" | "demo">("learner");
  const [code, setCode] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (actor && actor.mode !== "demo")
    return <Navigate to={roleHome(actor.role)} replace />;

  const chooseMode = (nextMode: "learner" | "staff" | "demo") => {
    setMode(nextMode);
    setError("");
  };

  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const isStaff = mode === "staff";
      const pair = await publicPost<TokenPair>(
        isStaff ? "/auth/staff/login" : "/auth/activate",
        isStaff
          ? { email: email.trim(), password }
          : { code: code.trim(), device: { platform: "web" } },
      );

      if (!mobileRoles.includes(pair.role as Role)) {
        if (pair.role === "reviewer") {
          throw new Error(
            "Không gian thẩm định nội dung hiện được mở trên giao diện web.",
          );
        }
        throw new Error("Vai trò này chưa thuộc phạm vi ứng dụng mobile.");
      }

      (pair.role === "learner" ? session : staffSession).signIn(pair);
      setActor({
        role: pair.role as Role,
        mode: "live",
        name: pair.role === "learner" ? "Người học" : "Cán bộ",
        id: `live-${pair.role}`,
      });
      const next = safeNextPath(params.get("next"));
      navigate(
        pair.consent_required
          ? `/dong-y${next ? `?next=${encodeURIComponent(next)}` : ""}`
          : (next ?? roleHome(pair.role as Role)),
        { replace: true },
      );
    } catch (cause) {
      setError((cause as Error).message);
      setBusy(false);
    }
  };

  return (
    <main className="mobile-login" id="main-content">
      <header className="login-brand">
        <span className="login-brand-kicker">Y HỌC DỰ PHÒNG</span>
        <strong>DocPrep</strong>
        <span>Ôn thi năng lực hành nghề</span>
      </header>

      <section className="login-body" aria-labelledby="login-title">
        <div className="login-intro">
          <h1 id="login-title">
            {mode === "demo" ? "Trải nghiệm DocPrep" : "Đăng nhập"}
          </h1>
          <p className="muted">
            {mode === "demo"
              ? "Dữ liệu mẫu để xem trước các màn hình chính."
              : "Chọn đúng loại tài khoản để tiếp tục."}
          </p>
        </div>

        {mode !== "demo" ? (
          <>
            <div
              className="login-type-switch"
              role="group"
              aria-label="Loại tài khoản"
            >
              <button
                type="button"
                aria-pressed={mode === "learner"}
                onClick={() => chooseMode("learner")}
              >
                Người học
              </button>
              <button
                type="button"
                aria-pressed={mode === "staff"}
                onClick={() => chooseMode("staff")}
              >
                Cán bộ
              </button>
            </div>

            <form className="stack login-form" onSubmit={login}>
              {mode === "learner" ? (
                <>
                  <label className="field" htmlFor="activation-code">
                    Mã kích hoạt
                    <input
                      id="activation-code"
                      name="code"
                      autoComplete="one-time-code"
                      autoCapitalize="characters"
                      placeholder="Nhập mã do cơ sở đào tạo cấp"
                      required
                      minLength={6}
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                    />
                  </label>
                  <p className="login-hint">
                    Mã kích hoạt dùng để tạo hoặc mở tài khoản học tập của bạn.
                  </p>
                </>
              ) : (
                <>
                  <label className="field" htmlFor="staff-email">
                    Email công vụ
                    <input
                      id="staff-email"
                      name="email"
                      type="email"
                      autoComplete="username"
                      inputMode="email"
                      placeholder="ten@donvi.gov.vn"
                      required
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </label>
                  <div className="field">
                    <label htmlFor="staff-password">Mật khẩu</label>
                    <span className="login-password-field">
                      <input
                        id="staff-password"
                        name="password"
                        type={showPassword ? "text" : "password"}
                        autoComplete="current-password"
                        required
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                      />
                      <button
                        type="button"
                        className="login-password-toggle"
                        aria-label={
                          showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"
                        }
                        aria-pressed={showPassword}
                        onClick={() => setShowPassword((visible) => !visible)}
                      >
                        {showPassword ? (
                          <EyeOff size={19} />
                        ) : (
                          <Eye size={19} />
                        )}
                      </button>
                    </span>
                  </div>
                  <p className="login-hint">
                    Dành cho cán bộ xem báo cáo và quản trị viên. Tài khoản
                    chuyên gia thẩm định dùng giao diện web.
                  </p>
                </>
              )}

              {error && (
                <p className="warn" role="alert">
                  {error}
                </p>
              )}

              <button className="btn primary login-submit" disabled={busy}>
                {busy
                  ? "Đang xác thực…"
                  : mode === "learner"
                    ? "Kích hoạt và đăng nhập"
                    : "Đăng nhập"}
                {!busy && <ArrowRight size={18} aria-hidden="true" />}
              </button>
            </form>

            <button
              type="button"
              className="login-demo-link"
              onClick={() => chooseMode("demo")}
            >
              Dùng dữ liệu trải nghiệm
            </button>
          </>
        ) : (
          <div className="stack login-demo-list">
            <p className="login-hint">
              Dữ liệu minh họa được lưu trên thiết bị này, không cần tài khoản
              máy chủ.
            </p>
            {demoProfiles.map(({ role, id, name, label, Icon }) => (
              <button
                className="demo-login-row"
                key={id}
                onClick={() => {
                  onDemoStart();
                  resetDemo();
                  setActor({ role, id, name, mode: "demo" });
                  clearWorkspace();
                  navigate(safeNextPath(params.get("next")) ?? roleHome(role));
                }}
              >
                <Icon size={20} aria-hidden="true" />
                <strong>{label}</strong>
                <ArrowRight size={17} aria-hidden="true" />
              </button>
            ))}
            <button
              type="button"
              className="login-demo-link"
              onClick={() => chooseMode("learner")}
            >
              Quay lại đăng nhập
            </button>
          </div>
        )}

        <footer className="login-footer">
          <Link to="/quyen-rieng-tu">Quyền riêng tư</Link>
          <span aria-hidden="true">·</span>
          <Link to="/dieu-khoan">Điều khoản</Link>
          <span aria-hidden="true">·</span>
          <Link to="/faq">Trợ giúp</Link>
        </footer>
      </section>
    </main>
  );
}
