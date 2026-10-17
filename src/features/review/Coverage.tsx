import { useActor } from "../../app/identity";
import { FutureNotice } from "../../components/ui/CapabilityNotice";
import { seed } from "../../lib/demo/store";
export function Coverage() {
  const actor = useActor()!;
  return (
    <div>
      <header className="page-heading">
        <h1>Ma trận bao phủ</h1>
        <p>Liên kết vấn đề cốt lõi, học liệu và câu hỏi.</p>
      </header>
      <FutureNotice release="api" name="Ma trận bao phủ" />
      {actor.mode === "demo" && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nhóm năng lực</th>
                <th>Vấn đề cốt lõi</th>
                <th>Câu minh họa được gắn mã</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {seed.blueprint.groups.flatMap((g: any) =>
                g.issues.map((i: any) => {
                  const n = seed.questions.filter(
                    (q: any) =>
                      q.competency_code ===
                      `CI-${String(i.id).padStart(2, "0")}`,
                  ).length;
                  return (
                    <tr key={i.id}>
                      <td>{g.short_name}</td>
                      <td>
                        {i.id}. {i.name}
                      </td>
                      <td>{n}</td>
                      <td>{n ? "Có mẫu chưa thẩm định" : "Chưa có dữ liệu"}</td>
                    </tr>
                  );
                }),
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
