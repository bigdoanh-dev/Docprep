import { Component, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

class ScreenBoundary extends Component<
  { resetKey: string; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidUpdate(
    previous: Readonly<{ resetKey: string; children: ReactNode }>,
  ) {
    if (this.state.failed && previous.resetKey !== this.props.resetKey) {
      this.setState({ failed: false });
    }
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="screen" id="main-content">
        <div className="body stack" role="alert">
          <h1>Chưa thể hiển thị trang này</h1>
          <p>Bạn có thể tải lại trang hoặc quay về trang chủ để tiếp tục.</p>
          <button
            className="btn primary"
            onClick={() => window.location.reload()}
          >
            Tải lại trang
          </button>
          <Link className="btn" to="/">
            Về trang chủ
          </Link>
        </div>
      </main>
    );
  }
}

export function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  return (
    <ScreenBoundary resetKey={location.pathname + location.search}>
      {children}
    </ScreenBoundary>
  );
}
