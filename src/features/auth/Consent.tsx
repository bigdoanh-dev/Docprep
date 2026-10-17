import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { LoadError, Loading } from "../../components/Status";
import { ApiError, api, signOut, type ConsentText } from "../../lib/api";
import { useLoad } from "../../lib/hooks";

// Only a path inside the app is followed after consent.
function safeNext(next: string | null): string {
  return next &&
    next.startsWith("/") &&
    !next.startsWith("//") &&
    !next.startsWith("/dong-y")
    ? next
    : "/";
}

// Consent, shown after sign-in and whenever the server asks for the current version: the service
// consent is required, the research consent is separate and optional (FR-ADM-03).
export function Consent() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { data, error, reload } = useLoad(
    () => api.get<ConsentText>("/consent/current"),
    [],
  );
  const [service, setService] = useState(false);
  const [research, setResearch] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string>();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!data || !service) return;
    setBusy(true);
    setNotice(undefined);
    try {
      await api.post("/consent", {
        version: data.version,
        service: true,
        research,
      });
      navigate(safeNext(params.get("next")), { replace: true });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // The texts changed while this screen was open: consent must be given to what is shown.
        setService(false);
        setResearch(false);
        setNotice("Nội dung đã được cập nhật. Vui lòng đọc lại.");
        reload();
      } else {
        setNotice((e as Error).message);
      }
      setBusy(false);
    }
  };

  return (
    <form className="screen" onSubmit={submit}>
      <div className="body stack" style={{ padding: 20, gap: 16 }}>
        <h1 className="title" style={{ marginTop: 12 }}>
          Trước khi bắt đầu
        </h1>
        {error && <LoadError message={error} onRetry={reload} />}
        {!data && !error && <Loading />}
        {data && (
          <>
            <section className="card stack">
              <p>{data.service_text_vi}</p>
              <label className="check">
                <input
                  type="checkbox"
                  checked={service}
                  onChange={(e) => setService(e.target.checked)}
                  disabled={busy}
                />
                Tôi đồng ý (bắt buộc)
              </label>
            </section>
            <section className="card stack">
              <p>{data.research_text_vi}</p>
              <label className="check">
                <input
                  type="checkbox"
                  checked={research}
                  onChange={(e) => setResearch(e.target.checked)}
                  disabled={busy}
                />
                Tôi đồng ý (không bắt buộc, có thể rút lại bất cứ lúc nào)
              </label>
            </section>
          </>
        )}
        {notice && (
          <p className="warn" role="alert">
            {notice}
          </p>
        )}
      </div>
      <div className="footer" style={{ flexDirection: "column" }}>
        <button
          className="btn primary block lg"
          type="submit"
          disabled={!data || !service || busy}
        >
          Tiếp tục
        </button>
        <button
          className="link-btn"
          type="button"
          onClick={() => signOut()}
          disabled={busy}
        >
          Đăng xuất
        </button>
      </div>
    </form>
  );
}
