import { useState } from "react";
import { Link } from "react-router-dom";
import type { SessionToday, StepKind } from "../lib/api";
import { stepStates } from "../lib/flow";
import { Icon } from "./Icon";

const STATE_TEXT = { done: "đã xong", current: "đang làm", todo: "sắp tới" };

// The top of every step of Phiên hôm nay: close, the count, one bar segment per step the session
// has, and the reasons for the order as the server gave them ("Vì sao thứ tự này?").
export function SessionHeader({
  session,
  current,
  countLabel,
}: {
  session: SessionToday | undefined;
  current: StepKind;
  countLabel?: string;
}) {
  const [whyOpen, setWhyOpen] = useState(false);
  return (
    <header
      className="topbar"
      style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}
    >
      <div className="row">
        <Link to="/" className="icon-btn" aria-label="Đóng phiên">
          <Icon name="close" />
        </Link>
        <h1>Phiên hôm nay</h1>
        {countLabel && (
          <span className="muted" style={{ fontWeight: 500 }}>
            {countLabel}
          </span>
        )}
      </div>
      {session && (
        <>
          <ol className="steps" role="list" aria-label="Các bước của phiên">
            {stepStates(session, current).map((s) => (
              <li
                key={s.kind}
                className={s.state}
                aria-current={s.state === "current" ? "step" : undefined}
              >
                <span className="bar" />
                {s.label}
                <span className="sr">, {STATE_TEXT[s.state]}</span>
              </li>
            ))}
          </ol>
          <div>
            <button
              className="textlink small muted"
              aria-expanded={whyOpen}
              aria-controls="session-reasons"
              onClick={() => setWhyOpen(!whyOpen)}
            >
              Vì sao thứ tự này?
            </button>
            {whyOpen && (
              <ul
                id="session-reasons"
                className="small"
                style={{
                  margin: "0 0 6px",
                  paddingLeft: 18,
                  color: "var(--text-2)",
                }}
              >
                {session.steps.map((s, i) => (
                  <li key={s.kind}>
                    {stepStates(session, current)[i].label}: {s.reason_vi}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </header>
  );
}
