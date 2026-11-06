import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AdaptationLines } from "../../components/AdaptationLines";
import { Icon } from "../../components/Icon";
import { PracticeRunner } from "../../components/PracticeRunner";
import { SessionHeader } from "../../components/SessionHeader";
import { api, type AdaptationSummary, type SessionToday } from "../../lib/api";
import { useLoad } from "../../lib/hooks";
import { useActor } from "../../app/identity";

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
// ends with a plain result instead of the adapting screen. Keyed by id: a next round is a new run.
export function PracticeSet() {
  const { setId } = useParams();
  return <PracticeSetRun key={setId} setId={setId!} />;
}

function PracticeSetRun({ setId }: { setId: string }) {
  const [summary, setSummary] = useState<AdaptationSummary>();
  const header = (countLabel?: string) => (
    <header className="topbar">
      <Link to="/on-tap" className="icon-btn" aria-label="Đóng bộ câu luyện">
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
            Bạn đã hoàn thành lượt ôn!
          </h2>
          <div className="card">
            <AdaptationLines summary={summary} />
          </div>
          <NextRound setId={setId} summary={summary} />
          <Link to="/on-tap" className="btn lg block">
            Về trang ôn tập
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

// From this share of correct answers on, the other round offered is a harder one; below it, a
// lighter one. Both are worded alike: an offer of what to do next, not a judgement of the score.
const STRETCH_FROM = 0.7;

function NextRound({
  setId,
  summary,
}: {
  setId: string;
  summary: AdaptationSummary;
}) {
  const actor = useActor();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  if (actor?.mode === "live") return <p className="muted">Tạo lượt ôn tùy chọn chưa được hỗ trợ. Bạn có thể tiếp tục phiên học hôm nay.</p>;
  const { correct, total } = summary.graded;
  const options = [
    {
      level: "same",
      title: "Làm thêm một lượt cùng mức",
      // No count: the bank skips questions answered this week, so a round may come out shorter.
      sub: "Câu hỏi khác trong cùng phạm vi",
    },
    total > 0 && correct / total >= STRETCH_FROM
      ? {
          level: "harder",
          title: "Thử một lượt thử thách hơn",
          sub: "Ưu tiên vấn đề cần luyện thêm và câu mức phân tích",
        }
      : {
          level: "easier",
          title: "Thử một lượt nhẹ nhàng hơn",
          sub: "Ít câu hơn, ở các vấn đề bạn đã nắm chắc hơn",
        },
  ];
  const start = async (level: string) => {
    setBusy(level);
    setError("");
    try {
      const set = await api.post<{ id: number }>("/practice-sets", {
        from_set: Number(setId),
        level,
      });
      navigate(`/luyen-tap/bo-cau/${set.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  };
  return (
    <section className="stack" aria-labelledby="next-round-title">
      <p id="next-round-title" className="label">
        Lượt tiếp theo
      </p>
      {options.map((o, i) => (
        <button
          key={o.level}
          className={`btn lg block next-round${i === 0 ? " primary" : ""}`}
          disabled={busy !== null}
          onClick={() => start(o.level)}
        >
          <span>
            <strong>{busy === o.level ? "Đang chuẩn bị…" : o.title}</strong>
            <small>{o.sub}</small>
          </span>
          <Icon name="right" size={20} />
        </button>
      ))}
      {error && (
        <p className="warn" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
