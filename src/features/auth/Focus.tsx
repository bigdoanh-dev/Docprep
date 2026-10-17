import { LearnerProfilePanel } from "../workspace/LearnerProfilePanel";
import { useState } from "react";
import {
  Link,
  useNavigate,
  useOutletContext,
  useSearchParams,
} from "react-router-dom";
import { Icon } from "../../components/Icon";
import { LoadError, Loading } from "../../components/Status";
import {
  api,
  type ExamForm,
  type Listed,
  type Me,
  type Module,
  type ModuleDetail,
} from "../../lib/api";
import { useLoad } from "../../lib/hooks";

// What the signed-in shell gives its screens: a way to say that the learner has now chosen.
export type GateContext = { focusChosen: () => void };

// The first unfinished unit of the first chosen học phần that has one; Home when none has.
async function firstUnitPath(chosen: Module[]): Promise<string> {
  for (const m of chosen) {
    if (m.coming_soon || m.units_total === 0) continue;
    const detail = await api.get<ModuleDetail>(`/modules/${m.id}`);
    const unit = detail.units.find((u) => !u.done);
    if (unit) return `/luyen-tap/${unit.id}`;
  }
  return "/";
}

async function diagnosticPath(): Promise<string> {
  const forms = await api.get<Listed<ExamForm>>("/exams");
  const form = forms.items.find((f) => f.kind === "diagnostic");
  return form ? `/thi-thu/${form.id}/quy-dinh` : "/thi-thu";
}

// Chọn học phần (FR-LRN-36, 37): shown once after consent, and again from "Đổi học phần" on Home.
// The choice orders what the learner is offered first; it can be changed at any time.
export function Focus() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const changing = params.get("doi") === "1";
  const { focusChosen } = useOutletContext<GateContext>();
  const { data, error, reload } = useLoad(async () => {
    const [modules, me] = await Promise.all([
      api.get<Listed<Module>>("/modules"),
      api.get<Me>("/me"),
    ]);
    return { modules: modules.items, focus: me.focus_module_ids, me };
  }, []);
  const [picked, setPicked] = useState<string[]>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string>();

  const selected = picked ?? data?.focus ?? [];
  const toggle = (id: string) =>
    setPicked(
      selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id],
    );

  const save = async (next: (chosen: Module[]) => Promise<string>) => {
    if (!data || busy || selected.length === 0) return;
    setBusy(true);
    setNotice(undefined);
    try {
      const chosen = data.modules.filter((m) => selected.includes(m.id));
      await api.patch<Me>("/me", {
        focus_module_ids: chosen.map((m) => m.id),
        diagnostic_prompt_dismissed: true,
      });
      const to = await next(chosen);
      focusChosen();
      navigate(to, { replace: true });
    } catch (e) {
      setNotice((e as Error).message);
      setBusy(false);
    }
  };

  const none = selected.length === 0;
  return (
    <div className="screen">
      {data && <LearnerProfilePanel me={data.me} />}
      <div className="body stack" style={{ padding: 20, gap: 14 }}>
        {changing ? (
          <div>
            <Link to="/" className="icon-btn" aria-label="Về trang chủ">
              <Icon name="close" />
            </Link>
          </div>
        ) : (
          <p className="label primary" style={{ marginTop: 12 }}>
            Bước cuối
          </p>
        )}
        <h1 className="title">Bạn muốn tập trung ôn chủ đề nào?</h1>
        <p className="muted">Chủ đề có thể được cập nhật bất cứ lúc nào</p>
        {error && <LoadError message={error} onRetry={reload} />}
        {!data && !error && <Loading />}
        {data?.modules.map((m) => {
          const on = selected.includes(m.id);
          return (
            <label
              key={m.id}
              className="card check"
              style={
                on
                  ? {
                      borderColor: "var(--primary)",
                      background: "var(--primary-tint)",
                      padding: "12px 16px",
                    }
                  : { padding: "12px 16px" }
              }
            >
              <input
                type="checkbox"
                checked={on}
                onChange={() => toggle(m.id)}
                disabled={busy}
              />
              <span className="grow">
                <span className="h2" style={{ display: "block" }}>
                  {m.short_name}
                </span>
                <span className="muted small">
                  {m.coming_soon || m.units_total === 0
                    ? "Sắp có"
                    : `${m.units_total} chủ đề`}
                </span>
              </span>
            </label>
          );
        })}
        {notice && (
          <p className="warn" role="alert">
            {notice}
          </p>
        )}
      </div>
      <div className="footer" style={{ flexDirection: "column", gap: 8 }}>
        <p className="muted small center" aria-live="polite">
          {none
            ? "Chọn ít nhất một học phần"
            : `Đã chọn ${selected.length} học phần`}
        </p>
        {changing ? (
          <button
            className="btn primary block lg"
            onClick={() => save(async () => "/")}
            disabled={!data || none || busy}
          >
            Lưu
          </button>
        ) : (
          <>
            <button
              className="btn primary block lg"
              onClick={() => save(diagnosticPath)}
              disabled={!data || none || busy}
            >
              Làm bài đánh giá năng lực
            </button>
            <button
              className="btn block lg"
              onClick={() => save(firstUnitPath)}
              disabled={!data || none || busy}
            >
              Bỏ qua, vào học ngay
            </button>
            <p className="muted small center">
              Bạn có thể mở bài đánh giá trong Học tập → Thi thử.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
