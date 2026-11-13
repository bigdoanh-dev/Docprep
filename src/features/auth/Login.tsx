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
import { session, staffSession } from "../../lib/client";
import { usernameLogin } from "../../lib/login";
import { clearWorkspace } from "../../lib/learnerWorkspace";
import { resetDemo } from "../../lib/demo/store";
import { RuntimeNotice } from "../../components/RuntimeNotice";

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
  const [signedInPath, setSignedInPath] = useState<string | null>(null);

  if (actor && actor.mode !== "demo")
    return (
      <Navigate
        to={
          signedInPath ??
          safeNextPath(params.get("next")) ??
          roleHome(actor.role)
        }
        replace
      />
    );

  const chooseMode = (nextMode: "learner" | "demo") => {
    if (busy) return;
    setMode(nextMode);
    setError("");
  };

  // The Phase 1 API returns the real role, consent status and rotating token pair.
  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    if (!username.trim()) {
      setError("Vui lòng nhập tên đăng nhập.");
      return;
    }
    setBusy(true);
    setError("");

    try {
      const signedIn = await usernameLogin(username.trim(), password);
      if (!["learner", "admin", "ministry_viewer"].includes(signedIn.role)) {
        throw new Error(
          "Không gian thẩm định nội dung hiện được mở trên giao diện web.",
        );
      }
      (signedIn.role === "learner" ? session : staffSession).signIn(signedIn);
      const next = safeNextPath(params.get("next"));
      setSignedInPath(
        signedIn.consent_required
          ? `/dong-y${next ? `?next=${encodeURIComponent(next)}` : ""}`
          : (next ?? roleHome(signedIn.role as Role)),
      );
      setActor({
        role: signedIn.role as Role,
        mode: "live",
        name: signedIn.role === "learner" ? "Người học" : "Cán bộ",
        id: `live-${signedIn.role}`,
      });
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
        <RuntimeNotice />
        <div className="login-intro">
          <h1 id="login-title">
            {mode === "demo" ? "Trải nghiệm DocPrep" : "Đăng nhập"}
          </h1>
          {mode === "demo" && (
            <p className="muted">
              Dữ liệu mẫu để xem trước các màn hình chính.
            </p>
          )}
        </div>

        {mode !== "demo" ? (
          <>
            <form className="stack login-form" onSubmit={login}>
              <label className="field" htmlFor="login-username">
                Tên đăng nhập
                <input
                  id="login-username"
                  name="username"
                  placeholder="Tên đăng nhập hoặc email cán bộ"
                  autoComplete="username"
                  autoCapitalize="none"
                  required
                  disabled={busy}
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
                    disabled={busy}
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

            <button
              type="button"
              className="login-demo-link"
              disabled={busy}
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
