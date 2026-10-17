import { scheduleError } from "./schedule";
import { Plus, UsersRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { useActor } from "../../app/identity";
import { Sheet } from "../../components/Sheet";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { useFeedback } from "../../components/ui/Feedback";
import { demoTransaction, readStore } from "../../lib/demo/store";
export function Lecturer() {
  const actor = useActor()!,
    notify = useFeedback(),
    loc = useLocation(),
    [revision, setRevision] = useState(0),
    [open, setOpen] = useState<"class" | "exam" | null>(null),
    [name, setName] = useState(""),
    [school, setSchool] = useState("CSDT-A"),
    [classId, setClassId] = useState("lop-01"),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [minutes, setMinutes] = useState(50),
    [notice, setNotice] = useState("");
  const s =
    actor.mode === "demo" ? readStore() : { classes: [], schedules: [] };
  const kind = loc.pathname.endsWith("/lich-thi")
    ? "exam"
    : loc.pathname.endsWith("/ket-qua")
      ? "results"
      : "class";
  const save = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setNotice("");
    const values = new FormData(e.currentTarget);
    const startValue = String(values.get("start") ?? start),
      endValue = String(values.get("end") ?? end);
    const error =
      open === "exam" ? scheduleError(startValue, endValue, minutes) : null;
    if (error) {
      setNotice(error);
      notify(error, "error");
      return;
    }
    demoTransaction((state) => {
      if (open === "class")
        state.classes.push({
          id: `lop-${++state.nextId}`,
          name: name.trim(),
          school,
          learners: 0,
          teacher: actor.name,
        });
      else
        state.schedules.push({
          id: ++state.nextId,
          title: name.trim(),
          classId,
          start: startValue,
          end: endValue,
          minutes,
          status: "scheduled",
        });
      return null;
    });
    setOpen(null);
    setName("");
    setRevision(revision + 1);
    notify(
      open === "class"
        ? "Đã tạo lớp minh họa."
        : "Đã lưu lịch thi minh họa. Không gửi thư mời thật.",
    );
  };
  return (
    <div>
      <header className="page-heading heading-actions">
        <div>
          <h1>
            {kind === "exam"
              ? "Lịch thi thử"
              : kind === "results"
                ? "Kết quả học tập của lớp"
                : "Không gian giảng viên"}
          </h1>
          <p>
            Quản lý lớp, phân công thi thử và theo dõi kết quả theo năng lực.
          </p>
        </div>
        <button
          className="btn primary"
          disabled={actor.mode !== "demo" || kind === "results"}
          onClick={() => {
            setOpen(kind === "exam" ? "exam" : "class");
            setNotice("");
          }}
        >
          <Plus size={18} />
          {kind === "exam" ? "Lập lịch thi" : "Tạo lớp"}
        </button>
      </header>
      <FutureNotice release="api" name="Cổng giảng viên và quản lý lớp" />
      <div className="workspace-tabs">
        <Link to="/giang-vien/lop">Lớp học</Link>
        <Link to="/giang-vien/lich-thi">Lịch thi</Link>
        <Link to="/giang-vien/ket-qua">Kết quả</Link>
      </div>
      {kind === "class" ? (
        <div className="class-list">
          {s.classes.map((c: any) => (
            <article className="panel" key={c.id}>
              <UsersRound size={26} />
              <h2>{c.name}</h2>
              <p>
                {c.school} · {c.learners} học viên minh họa
              </p>
              <p className="muted">{c.teacher}</p>
              <button
                className="btn"
                onClick={() => {
                  setClassId(c.id);
                  setOpen("exam");
                }}
                disabled={actor.mode !== "demo"}
              >
                Phân công thi thử
              </button>
            </article>
          ))}
        </div>
      ) : kind === "exam" ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Bài thi</th>
                <th>Lớp</th>
                <th>Mở bài</th>
                <th>Kết thúc</th>
                <th>Thời lượng</th>
              </tr>
            </thead>
            <tbody>
              {s.schedules.map((e: any) => (
                <tr key={e.id}>
                  <td>{e.title}</td>
                  <td>
                    {s.classes.find((c: any) => c.id === e.classId)?.name}
                  </td>
                  <td>{new Date(e.start).toLocaleString("vi-VN")}</td>
                  <td>{new Date(e.end).toLocaleString("vi-VN")}</td>
                  <td>{e.minutes} phút</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!s.schedules.length && (
            <p className="empty">
              Chưa có lịch thi. Tạo lịch sau khi đã có lớp và đề được duyệt.
            </p>
          )}
        </div>
      ) : (
        <section className="panel">
          <h2>Chưa có bộ dữ liệu kết quả của lớp</h2>
          <p>
            Kết quả tổng hợp cần liên kết người học, lớp, bài thi, phiên bản và
            đồng thuận. Không dùng bảng số liệu mẫu để kết luận hiệu quả can
            thiệp.
          </p>
        </section>
      )}
      <Sheet
        open={!!open}
        onClose={() => setOpen(null)}
        title={
          open === "class"
            ? "Tạo lớp học minh họa"
            : "Lập lịch thi thử minh họa"
        }
      >
        <form className="stack" onSubmit={save}>
          <label className="field">
            {open === "class" ? "Tên lớp" : "Tên bài thi"}
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={100}
            />
          </label>
          {open === "class" ? (
            <label className="field">
              Mã cơ sở đào tạo
              <input
                value={school}
                onChange={(e) => setSchool(e.target.value)}
                required
              />
            </label>
          ) : (
            <>
              <label className="field">
                Lớp học
                <select
                  value={classId}
                  onChange={(e) => setClassId(e.target.value)}
                >
                  {s.classes.map((c: any) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Mở bài
                <input
                  type="datetime-local"
                  name="start"
                  required
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
              </label>
              <label className="field">
                Kết thúc
                <input
                  type="datetime-local"
                  name="end"
                  required
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                />
              </label>
              <label className="field">
                Thời lượng (phút)
                <input
                  type="number"
                  min={10}
                  max={240}
                  value={minutes}
                  onChange={(e) => setMinutes(Number(e.target.value))}
                />
              </label>
              <p className="notice">
                Cần chọn đề đã duyệt khi tích hợp thật. Luồng minh họa này không
                gửi lời mời hoặc tạo phòng thi thật.
              </p>
            </>
          )}
          {notice && (
            <p className="warn" role="alert">
              {notice}
            </p>
          )}
          <button className="btn primary" disabled={actor.mode !== "demo"}>
            Lưu minh họa
          </button>
        </form>
      </Sheet>
    </div>
  );
}
