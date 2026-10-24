import { useState } from "react";
import {
  api,
  type ChatState,
  type Citation,
  type PassageView,
} from "../lib/api";
import { useLoad } from "../lib/hooks";
import { Sheet } from "./Sheet";
import { LoadError, Loading } from "./Status";

export type AnswerResult = {
  state: ChatState;
  text: string;
  citations: Citation[];
  notice: string | null;
};
export type StreamStatus = "queued" | "answering" | "checking_sources";

const STATUS_COPY: Record<StreamStatus, string> = {
  queued: "Đang xếp hàng…",
  answering: "Đang tìm trong tài liệu…",
  checking_sources: "Đang kiểm tra nguồn…",
};

export function sourceLine(c: {
  chapter: string | null;
  section: string | null;
  page: number | null;
  article: string | null;
}) {
  return [c.chapter, c.section, c.page ? `trang ${c.page}` : c.article]
    .filter(Boolean)
    .join(" · ");
}

export function CitationChip({
  citation,
  label,
  onOpen,
}: {
  citation: Citation;
  label?: string;
  onOpen: (c: Citation) => void;
}) {
  const where = citation.page ? `trang ${citation.page}` : citation.article;
  return (
    <button
      className={label ? "chip" : "cite"}
      onClick={() => onOpen(citation)}
      aria-label={`Nguồn ${citation.n}: ${citation.document}, ${where}`}
    >
      {label
        ? `${citation.document} · ${where ?? "Tài liệu nguồn"}`
        : citation.n}
    </button>
  );
}

// Source view: the passage behind a citation, opened over the current screen.
export function SourceSheet({
  citation,
  onClose,
}: {
  citation: Citation | null;
  onClose: () => void;
}) {
  return (
    <Sheet
      open={citation !== null}
      onClose={onClose}
      title={citation ? `Nguồn ${citation.n}` : "Nguồn"}
    >
      {citation && <SourceBody passageId={citation.passage_id} />}
    </Sheet>
  );
}

function SourceBody({ passageId }: { passageId: string }) {
  const { data, error, reload } = useLoad(
    () => api.get<PassageView>(`/passages/${passageId}`),
    [passageId],
  );
  if (error) return <LoadError message={error} onRetry={reload} />;
  if (!data) return <Loading />;
  return (
    <div className="stack">
      <div>
        <div className="h2">{data.document}</div>
        <div className="muted small">{sourceLine(data)}</div>
      </div>
      {data.validity_note && <p className="warn">{data.validity_note}</p>}
      <p className="reading">{data.excerpt}</p>
      <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
        <span className="tag">{data.demo_label}</span>
      </div>
    </div>
  );
}

// `position`: the learner's real place in the queue, sent by the server while the request waits.
export function StatusLine({
  status,
  position,
}: {
  status: StreamStatus;
  position?: number;
}) {
  return (
    <div className="row muted" role="status">
      <span className="spinner" />
      {status === "queued" && position
        ? `Đang xếp hàng, vị trí ${position}…`
        : STATUS_COPY[status]}
    </div>
  );
}

// Answer text with its [n] markers turned into tappable citation chips.
export function AnswerText({
  result,
  onCite,
}: {
  result: AnswerResult;
  onCite: (c: Citation) => void;
}) {
  const byN = new Map(result.citations.map((c) => [c.n, c]));
  const parts = result.text.split(/(\[\d+\])/g);
  return (
    <p style={{ fontSize: 16, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
      {parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part);
        const citation = m && byN.get(Number(m[1]));
        return citation ? (
          <CitationChip key={i} citation={citation} onOpen={onCite} />
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </p>
  );
}

// Hook for screens that show cited answers: holds which source is open.
export function useSourceSheet() {
  const [open, setOpen] = useState<Citation | null>(null);
  return {
    open,
    show: setOpen,
    sheet: <SourceSheet citation={open} onClose={() => setOpen(null)} />,
  };
}
