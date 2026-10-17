import { Link, Navigate, useLocation } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { LoadError, Loading } from "../../components/Status";
import { api, type DueCardList, type SessionToday } from "../../lib/api";
import { nextStep, stepPath } from "../../lib/flow";
import { useLoad } from "../../lib/hooks";

// The end of the day's session. Cards that came due after the session was built (from answers given
// during it) are still counted on Home, so they are offered here.
export function SessionDone({ note }: { note?: string }) {
  const { data: due } = useLoad(
    () => api.get<DueCardList>("/cards/due?limit=1"),
    [],
  );
  return (
    <div
      className="stack center"
      style={{ marginTop: 48, alignItems: "center" }}
    >
      <span
        className="icon-box"
        style={{ width: 64, height: 64, borderRadius: 32 }}
      >
        <Icon name="check" size={30} />
      </span>
      <h2 className="title">Xong phiên hôm nay</h2>
      {note && (
        <p className="muted" style={{ fontSize: 16 }}>
          {note}
        </p>
      )}
      <div className="stack" style={{ width: "100%", marginTop: 16 }}>
        {due && due.total_due > 0 && (
          <Link to="/luyen-tap/on-the" className="btn lg block">
            Ôn {due.total_due} thẻ đến hạn
          </Link>
        )}
        <Link to="/" className="btn primary lg block">
          Về trang chủ
        </Link>
      </div>
    </div>
  );
}

// /phien: Phiên hôm nay opens at its first unfinished step (FR-LRN-34, 36).
export function Session() {
  const note = (useLocation().state as { note?: string } | null)?.note; // from the step that just ended
  const { data, error, reload } = useLoad(
    () => api.get<SessionToday>("/session/today"),
    [],
  );
  if (error)
    return (
      <div className="screen">
        <div className="body">
          <LoadError message={error} onRetry={reload} />
        </div>
      </div>
    );
  if (!data)
    return (
      <div className="screen">
        <div className="body">
          <Loading />
        </div>
      </div>
    );
  const next = nextStep(data);
  if (next) return <Navigate to={stepPath(next)} replace />;
  return (
    <div className="screen">
      <div className="body">
        <SessionDone note={note} />
      </div>
    </div>
  );
}
