import { LearnerProfilePanel } from "../workspace/LearnerProfilePanel";
import {
  readWorkspace,
  clearWorkspace,
  useWorkspace,
  updateWorkspace,
} from "../../lib/learnerWorkspace";
import { DoctorAvatar } from "../../components/DoctorAvatar";
import { MascotPicker } from "../../components/MascotPicker";
import { Link } from "react-router-dom";
import {
  Download,
  LogOut,
  Settings2,
  ShieldCheck,
  Trash2,
  UserRound,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { roleNames, setActor, useActor } from "../../app/identity";
import { Sheet } from "../../components/Sheet";
import { LoadError, Loading } from "../../components/Status";
import { useFeedback } from "../../components/ui/Feedback";
import { api, signOut, type Me } from "../../lib/api";
import { resetDemo } from "../../lib/demo/store";
import { useLoad } from "../../lib/hooks";
export function saveFile(data: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = Object.assign(document.createElement("a"), {
    href: url,
    download: name,
  });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function Account() {
  const workspace = useWorkspace();
  const [gender, setGender] = useState(workspace.gender);
  const actor = useActor()!,
    notify = useFeedback();
  const { data, error, reload } = useLoad(
    async () =>
      actor.role === "learner" ? api.get<Me & { consent: any }>("/me") : null,
    [actor.id],
  );
  const [draft, setDraft] = useState<any>({}),
    [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState(""),
    [confirm, setConfirm] = useState<"delete" | "research" | "service" | null>(
      null,
    ),
    [phrase, setPhrase] = useState("");
  const values = { ...data, ...draft };
  const run = async (fn: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setActionError("");
    try {
      await fn();
    } catch (e) {
      setActionError((e as Error).message);
      notify((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };
  const save = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      const me = Object.keys(draft).length
        ? await api.patch<Me>("/me", draft)
        : data!;
      updateWorkspace((w) => ({ ...w, gender }));
      setActor({ ...actor, name: me.display_name });
      setDraft({});
      reload();
      notify("Đã lưu thông tin và cài đặt ôn tập.");
    });
  };
  return (
    <div className="settings-page">
      <header className="page-heading">
        <h1>{actor.role === "learner" ? "Profile" : "Tài khoản"}</h1>
      </header>
      <div className="account-summary">
        {actor.role === "learner" ? (
          <DoctorAvatar gender={gender} avatar />
        ) : (
          <span className="staff-account-avatar" aria-hidden="true">
            {actor.role === "admin" ? (
              <ShieldCheck size={30} />
            ) : (
              <UserRound size={30} />
            )}
          </span>
        )}
        <div>
          <h2>{data?.display_name ?? actor.name}</h2>
          <p>
            {roleNames[actor.role]} ·{" "}
            {actor.mode === "demo"
              ? "Trải nghiệm minh họa"
              : "Phiên kết nối máy chủ"}
          </p>
        </div>
      </div>
      {actor.role === "learner" && (
        <section className="profile-appearance">
          <fieldset>
            <legend>Hình đại diện</legend>
            <div className="gender-control">
              {(
                [
                  ["male", "Nam"],
                  ["female", "Nữ"],
                  [null, "Chưa chọn"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={label}
                  type="button"
                  aria-pressed={gender === value}
                  onClick={() => setGender(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </fieldset>
          <p className="muted small">
            Hình chào đổi theo lựa chọn của bạn. Lưu trên thiết bị này.
          </p>
          <MascotPicker />
        </section>
      )}
      {actor.role === "learner" && (
        <Link to="/thong-bao" className="btn">
          Cài đặt thông báo và nhắc học
        </Link>
      )}
      {error && <LoadError message={error} onRetry={reload} />}{" "}
      {actor.role === "learner" && !data && !error && <Loading />}
      {data && <LearnerProfilePanel me={data} />}
      {data && (
        <form onSubmit={save} className="settings-grid">
          <section className="panel stack">
            <h2>
              <Settings2 size={21} />
              Thông tin và lịch ôn
            </h2>
            <label className="field">
              Tên hiển thị
              <input
                value={values.display_name ?? ""}
                onChange={(e) =>
                  setDraft({ ...draft, display_name: e.target.value })
                }
                required
                maxLength={80}
              />
            </label>
            <label className="field">
              Ngày thi mục tiêu
              <input
                type="date"
                value={values.exam_date ?? ""}
                onChange={(e) =>
                  setDraft({ ...draft, exam_date: e.target.value || null })
                }
              />
            </label>
            <p className="muted small">
              Ngày do bạn đặt, không phải lịch thi quốc gia được xác nhận.
            </p>
            <label className="field">
              Mức nhớ mục tiêu
              <select
                value={values.target_retention}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    target_retention: Number(e.target.value),
                  })
                }
              >
                <option value={0.85}>85%</option>
                <option value={0.9}>90%</option>
                <option value={0.95}>95%</option>
              </select>
            </label>
            <div className="two-fields">
              <label className="field">
                Thẻ mới tối đa/ngày
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={values.new_cards_per_day}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      new_cards_per_day: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label className="field">
                Lượt ôn tối đa/ngày
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={values.max_reviews_per_day}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      max_reviews_per_day: Number(e.target.value),
                    })
                  }
                />
              </label>
            </div>
            <p className="notice small">
              Giới hạn số lượt đang được hoàn thiện ở dịch vụ hiện tại; danh
              sách đến hạn có thể chưa được cắt theo cài đặt.
            </p>
            <button
              className="btn primary"
              disabled={
                busy ||
                (!Object.keys(draft).length && gender === workspace.gender)
              }
            >
              {busy ? "Đang lưu…" : "Lưu thay đổi"}
            </button>
          </section>
          <section className="panel stack">
            <h2>
              <ShieldCheck size={21} />
              Quyền dữ liệu
            </h2>
            <p>
              Đồng ý nghiên cứu được quản lý riêng với quyền sử dụng dịch vụ học
              tập.
            </p>
            <p className="notice">
              {data.consent?.research_given_at
                ? "Bạn đã đồng ý sử dụng log cho nghiên cứu."
                : "Bạn chưa đồng ý sử dụng log cho nghiên cứu."}
            </p>
            <button
              type="button"
              className="btn"
              onClick={() =>
                run(async () => {
                  saveFile(
                    {
                      learning: await api.get("/me/data"),
                      browserWorkspace: readWorkspace(),
                    },
                    `du-lieu-ca-nhan-${actor.mode}.json`,
                  );
                  notify("Đã chuẩn bị tệp dữ liệu cá nhân.");
                })
              }
              disabled={busy}
            >
              <Download size={17} />
              Xuất dữ liệu của tôi
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => setConfirm("research")}
              disabled={!data.consent?.research_given_at || busy}
            >
              Rút đồng ý nghiên cứu
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => setConfirm("service")}
              disabled={busy}
            >
              Rút đồng ý dịch vụ
            </button>
            <button
              type="button"
              className="btn danger-outline"
              onClick={() => setConfirm("delete")}
              disabled={busy}
            >
              <Trash2 size={17} />
              Yêu cầu xóa tài khoản
            </button>
            <p className="muted small">
              Nhật ký bất biến và quy định lưu giữ cần được công bố đầy đủ trước
              khi vận hành thật.
            </p>
          </section>
        </form>
      )}
      <button className="btn profile-signout" onClick={() => signOut()}>
        <LogOut size={17} />
        Đăng xuất
      </button>
      {actor.mode === "demo" && (
        <section className="panel reset-panel">
          <h2>Dữ liệu trải nghiệm</h2>
          <p>
            Khôi phục các bài làm, hội thoại và quyết định minh họa ban đầu.
          </p>
          <button
            className="btn"
            onClick={() => {
              resetDemo();
              clearWorkspace();
              notify("Đã khôi phục dữ liệu minh họa.");
              if (actor.role === "learner") window.location.assign("/dong-y");
              else window.location.reload();
            }}
          >
            Khôi phục dữ liệu minh họa
          </button>
        </section>
      )}
      {actionError && (
        <p className="warn" role="alert">
          {actionError}
        </p>
      )}
      <Sheet
        open={!!confirm}
        onClose={() => !busy && setConfirm(null)}
        title={
          confirm === "delete"
            ? "Xác nhận yêu cầu xóa"
            : confirm === "service"
              ? "Rút đồng ý dịch vụ"
              : "Rút đồng ý nghiên cứu"
        }
      >
        <div className="stack">
          {confirm === "delete" ? (
            <>
              <p>
                Tài khoản và dữ liệu học sẽ được xử lý theo chính sách hiện
                hành. Phiên đăng nhập sẽ kết thúc.{" "}
                {actor.mode === "demo" &&
                  "Đây chỉ là dữ liệu trên trình duyệt."}
              </p>
              <label className="field">
                Nhập XÓA để xác nhận
                <input
                  value={phrase}
                  onChange={(e) => setPhrase(e.target.value)}
                  autoComplete="off"
                />
              </label>
            </>
          ) : (
            <p>
              {confirm === "service"
                ? "Bạn sẽ cần đồng ý lại trước khi tiếp tục học. Việc này không tự xóa dữ liệu đã lưu."
                : "Việc rút đồng ý nghiên cứu không tự hủy quyền sử dụng dịch vụ học tập."}
            </p>
          )}
          {actionError && (
            <p role="alert" className="warn">
              {actionError}
            </p>
          )}
          <button
            className="btn primary"
            disabled={busy || (confirm === "delete" && phrase !== "XÓA")}
            onClick={() =>
              run(async () => {
                if (confirm === "delete") {
                  await api.del("/me");
                  clearWorkspace();
                  await signOut();
                } else {
                  await api.del(
                    `/consent?kind=${confirm === "service" ? "service" : "research"}`,
                  );
                  if (confirm === "service") {
                    window.location.assign("/dong-y");
                    return;
                  }
                  setConfirm(null);
                  reload();
                  notify("Đã rút đồng ý nghiên cứu.");
                }
              })
            }
          >
            {busy ? "Đang xử lý…" : "Xác nhận"}
          </button>
          <button
            className="btn"
            onClick={() => setConfirm(null)}
            disabled={busy}
          >
            Quay lại
          </button>
        </div>
      </Sheet>
    </div>
  );
}
