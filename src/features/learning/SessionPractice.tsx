import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AdaptationLines } from "../../components/AdaptationLines";
import { Icon } from "../../components/Icon";
import { PracticeRunner } from "../../components/PracticeRunner";
import { SessionHeader } from "../../components/SessionHeader";
import { api, type AdaptationSummary, type SessionToday } from "../../lib/api";
import { useLoad } from "../../lib/hooks";

// Phiên hôm nay, step 2: the weak-spot set of the day. Finishing it opens "Phần hỏi đáp đang điều chỉnh".
export function SessionPractice() {
  const navigate = useNavigate();
  const { data: session } = useLoad(
    () => api.get<SessionToday>("/session/today"),
    [],
  );
  return (
    <PracticeRunner
      base="/session/today/practice"
      missingTo="/phien"
      contextLabel="Luyện điểm yếu"
      header={(countLabel) => (
        <SessionHeader
          session={session}
          current="practice"
          countLabel={countLabel}
        />
      )}
      onDone={(summary) =>
        navigate("/phien/dieu-chinh", { replace: true, state: { summary } })
      }
    />
  );
}

// Bộ câu luyện: a practice set opened by id, from a suggestion on Home. Outside the session, so it
// ends with a plain result instead of the adapting screen.
export function PracticeSet() {
  const { setId } = useParams();
  const [summary, setSummary] = useState<AdaptationSummary>();
  const header = (countLabel?: string) => (
    <header className="topbar">
      <Link to="/" className="icon-btn" aria-label="Đóng bộ câu luyện">
        <Icon name="close" />
      </Link>
      <h1>Bộ câu luyện</h1>
      {countLabel && (
        <span className="muted" style={{ fontWeight: 500 }}>
          {countLabel}
        </span>
      )}
    </header>
  );
  if (summary) {
    return (
      <div className="screen">
        {header()}
        <div className="body stack">
          <h2 className="title" style={{ marginTop: 12 }}>
            Đã xong bộ câu
          </h2>
          <div className="card">
            <AdaptationLines summary={summary} />
          </div>
          <Link to="/" className="btn primary lg block">
            Về trang chủ
          </Link>
        </div>
      </div>
    );
  }
  return (
    <PracticeRunner
      base={`/practice-sets/${setId}`}
      header={header}
      onDone={setSummary}
      contextLabel="Bộ câu luyện"
    />
  );
}
