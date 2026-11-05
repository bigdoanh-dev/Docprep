export function SetupProgress({ step }: { step: 1 | 2 }) {
  return (
    <ol className="setup-progress" aria-label="Tiến trình thiết lập">
      {["Đồng ý sử dụng", "Chọn chủ đề"].map((label, index) => (
        <li
          key={label}
          className={index + 1 <= step ? "active" : ""}
          aria-current={index + 1 === step ? "step" : undefined}
        >
          <span>{index + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  );
}
