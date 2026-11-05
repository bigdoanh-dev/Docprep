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
import { roleHome, setActor, useActor } from "../../app/identity";
import { session } from "../../lib/client";
import { liveLogin } from "../../lib/live/backend";
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
  const [mode, setMode] = useState<"learner" | "demo">("learner");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (actor && actor.mode !== "demo")
    return <Navigate to={roleHome(actor.role)} replace />;

  const chooseMode = (nextMode: "learner" | "demo") => {
    setMode(nextMode);
    setError("");
  };

  // The backend's own accounts (`yhdp user-add`): any of them studies as a learner. A reviewer also
  // has the reviewing tools, which are the separate app under /review/.
  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const signedIn = await liveLogin(username.trim(), password);
      session.signIn({ access_token: signedIn.token, refresh_token: "" });
      setActor({
        role: "learner",
        mode: "live",
        name: signedIn.username,
        id: signedIn.username,
      });
      navigate(safeNextPath(params.get("next")) ?? "/", { replace: true });
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
              : "Dùng tài khoản do quản trị viên cấp."}
          </p>
        </div>

        {mode !== "demo" ? (
          <>
            <form className="stack login-form" onSubmit={login}>
              <label className="field" htmlFor="login-username">
                Tên đăng nhập
                <input
                  id="login-username"
                  name="username"
                  autoComplete="username"
                  autoCapitalize="none"
                  required
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </label>
              <div className="field">
                <label htmlFor="login-password">Mật khẩu</label>
                <span className="login-password-field">
                  <input
                    id="login-password"
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
                    aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((visible) => !visible)}
                  >
                    {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
                  </button>
                </span>
              </div>

              {error && (
                <p className="warn" role="alert">
                  {error}
                </p>
              )}

              <button className="btn primary login-submit" disabled={busy}>
                {busy ? "Đang xác thực…" : "Đăng nhập"}
                {!busy && <ArrowRight size={18} aria-hidden="true" />}
              </button>
            </form>

            <p className="login-hint">
              Chuyên gia thẩm định nội dung:{" "}
              <a href="/review/">mở giao diện thẩm định</a>.
            </p>

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
