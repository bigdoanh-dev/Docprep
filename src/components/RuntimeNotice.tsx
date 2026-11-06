import { useEffect, useState } from "react";

type Runtime = { mode: string; model_provider: string; demo_content: boolean; service?: string };
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
  const version = info.service === "chat" ? "Phase 1" : "Alpha V1";
  return (
    <p className="demo-strip" role="note">
      {info.mode === "mock"
        ? "API mô phỏng — dữ liệu minh họa"
        : info.model_provider === "scripted"
          ? `${version} · AI mô phỏng — dữ liệu minh họa`
          : `${version} — dữ liệu minh họa`}
    </p>
  );
}
