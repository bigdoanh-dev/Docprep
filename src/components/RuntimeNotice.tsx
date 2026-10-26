import { useEffect, useState } from "react";

type Runtime = { mode: string; model_provider: string; demo_content: boolean };
let runtime: Promise<Runtime | null> | undefined;

export function RuntimeNotice() {
  const [info, setInfo] = useState<Runtime | null>(null);
  useEffect(() => {
    let active = true;
    runtime ??= fetch("/api/health")
      .then((response) =>
        response.ok ? (response.json() as Promise<Runtime>) : null,
      )
      .catch(() => null);
    runtime.then((value) => {
      if (active) setInfo(value);
    });
    return () => {
      active = false;
    };
  }, []);
  if (!info?.demo_content) return null;
  return (
    <p className="demo-strip" role="note">
      {info.mode === "mock"
        ? "API mô phỏng — dữ liệu minh họa"
        : info.model_provider === "scripted"
          ? "Alpha V1 · AI mô phỏng — dữ liệu minh họa"
          : "Alpha V1 — dữ liệu minh họa"}
    </p>
  );
}
