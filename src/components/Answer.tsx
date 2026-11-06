import { groupCitations } from "../lib/citations";
import { useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  const where = citation.page
    ? `trang ${citation.page}`
    : (citation.article ?? citation.chapter);
  return (
    <button
      className={label ? "chip" : "cite"}
      onClick={() => onOpen(citation)}
      aria-label={`Nguồn ${citation.n}: ${citation.document}${where ? `, ${where}` : ""}`}
    >
      {label
        ? `${citation.document} · ${where ?? "Tài liệu nguồn"}`
        : citation.n}
    </button>
  );
}

// Source view: the passage behind a citation, opened over the current screen.
export function QuestionSources({
  citations,
  onOpen,
}: {
  citations: Citation[];
  onOpen: (citation: Citation) => void;
}) {
  const groups = groupCitations(citations);
  return (
    <section
      className="stack"
      style={{ width: "100%", gap: 8 }}
      aria-label="Trích dẫn tài liệu"
    >
      <p className="label">Trích dẫn tài liệu</p>
      {citations.length > 0 ? (
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          {groups.map(([document, entries]) =>
            entries.length === 1 ? (
              <CitationChip
                key={document}
                citation={entries[0]}
                onOpen={onOpen}
                label="Nguồn"
              />
            ) : (
              <details key={document} className="source-group">
                <summary>
                  {document} · {entries.length} đoạn trích
                </summary>
                <div className="stack">
                  {entries.map((citation, index) => (
                    <button
                      type="button"
                      key={citation.passage_id}
                      className="chip"
                      onClick={() => onOpen(citation)}
                    >
                      Đoạn {index + 1}
                      {sourceLine(citation) ? ` · ${sourceLine(citation)}` : ""}
                    </button>
                  ))}
                </div>
              </details>
            ),
          )}
        </div>
      ) : (
        <p className="muted small">
          Câu hỏi này chưa được gắn tài liệu tham chiếu.
        </p>
      )}
    </section>
  );
}

export function ExplanationDetails({ children }: { children: ReactNode }) {
  return (
    <details className="explanation-details">
      <summary>Xem giải thích chi tiết</summary>
      <div className="stack">{children}</div>
    </details>
  );
}

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

// The model may break lines inside a table cell with <br>, the only HTML it writes. That tag
// becomes a line break; any other HTML stays escaped text.
type HastNode = {
  type: string;
  value?: string;
  children?: HastNode[];
} & Record<string, unknown>;
const lineBreaks = () => (tree: HastNode) => {
  const visit = (node: HastNode) =>
    node.children?.forEach((child, i) => {
      if (child.type === "raw" && /^<br\s*\/?>$/i.test(child.value ?? ""))
        node.children![i] = {
          type: "element",
          tagName: "br",
          properties: {},
          children: [],
        };
      else visit(child);
    });
  visit(tree);
};

const CITE_HREF = "#nguon-";

// The model sometimes writes arrows and signs as LaTeX ("$\rightarrow$"), which is not rendered
// here: they become the characters they stand for.
const LATEX: Record<string, string> = {
  rightarrow: "→",
  Rightarrow: "⇒",
  to: "→",
  leftarrow: "←",
  leftrightarrow: "↔",
  geq: "≥",
  ge: "≥",
  leq: "≤",
  le: "≤",
  times: "×",
  pm: "±",
  approx: "≈",
  uparrow: "↑",
  downarrow: "↓",
};
const symbols = (text: string) =>
  text.replace(/\$?\\([A-Za-z]+)\$?/g, (all, name) => LATEX[name] ?? all);

// Answer text: Markdown (headings, lists, tables), with its [n] markers as tappable citation chips.
export function AnswerText({
  result,
  onCite,
}: {
  result: AnswerResult;
  onCite: (c: Citation) => void;
}) {
  const byN = new Map(result.citations.map((c) => [c.n, c]));
  // [n] becomes a link the renderer hands back below; a number with no source stays as written.
  const text = symbols(result.text).replace(/\[(\d+)\](?!\()/g, (marker, n) =>
    byN.has(Number(n)) ? `[${n}](${CITE_HREF}${n})` : marker,
  );
  return (
    <div className="answer-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[lineBreaks]}
        components={{
          a: ({ href, children }) => {
            const citation =
              href?.startsWith(CITE_HREF) &&
              byN.get(Number(href.slice(CITE_HREF.length)));
            return citation ? (
              <CitationChip citation={citation} onOpen={onCite} />
            ) : (
              <a href={href} target="_blank" rel="noreferrer">
                {children as ReactNode}
              </a>
            );
          },
          table: ({ children }) => (
            <div className="answer-table">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
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
