import { AlertTriangle } from "lucide-react";
export function FutureNotice({
  name,
  release,
}: {
  name: string;
  release?: string;
}) {
  return (
    <div className="notice capability">
      <AlertTriangle size={20} />
      <div>
        <strong>
          {name}{" "}
          {release === "api"
            ? "chưa được triển khai đầy đủ trên máy chủ."
            : "thuộc phần mở rộng R1.1/R2."}
        </strong>
        <p>
          Máy chủ hiện tại chưa hỗ trợ đầy đủ thao tác này. Bản trải nghiệm cho
          phép xem và thử luồng với dữ liệu minh họa.
        </p>
      </div>
    </div>
  );
}
