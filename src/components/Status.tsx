// Shared loading and error states so every screen says the same thing the same way.
export function Loading({ label = "Đang tải…" }: { label?: string }) {
  return (
    <div
      className="empty row"
      style={{ justifyContent: "center" }}
      role="status"
    >
      <span className="spinner" />
      {label}
    </div>
  );
}

export function LoadError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="empty stack" role="alert">
      <p>{message}</p>
      {onRetry && (
        <div>
          <button className="btn" onClick={onRetry}>
            Thử lại
          </button>
        </div>
      )}
    </div>
  );
}
