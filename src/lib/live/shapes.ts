// The backend's payloads in the shapes the screens read: items, feedback, sources and times.
import blueprintJson from "../blueprint.json";
import type { Citation } from "../chatTurn";
import { localDay } from "../learnerWorkspace";
import type { LiveState } from "./store";

// Phone-card labels of the 8 đề mục; the backend has the official names only.
const SHORT = new Map<number, string>(
  (
    blueprintJson as { groups: { id: number; short_name: string }[] }
  ).groups.map((g) => [g.id, g.short_name]),
);
export const shortName = (deMuc: number, name = `Đề mục ${deMuc}`) =>
  SHORT.get(deMuc) ?? name;

/** SQLite's datetime('now') is UTC without a zone: "2026-11-04 08:00:00". */
export const isoUtc = (sqlite: string) => `${sqlite.replace(" ", "T")}Z`;
export const vnDay = (iso: string | Date) =>
  localDay(typeof iso === "string" ? new Date(iso) : iso);

export const toOptions = (options: Record<string, string>) =>
  Object.entries(options).map(([key, text]) => ({ key, text }));

/** The vignette with its question, as one stem. */
export const stemOf = (item: { stem: string; lead_in?: string | null }) =>
  item.lead_in ? `${item.stem}\n\n${item.lead_in}` : item.stem;

/** The backend cites as [S2]; the screens as [2]. */
export const cites = (text: string) => text.replace(/\[S(\d+)\]/g, "[$1]");

/** Plain text, for the fields shown without Markdown (explanations, rationales). */
export const plain = (text: string) =>
  cites(text)
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/^#{1,6}\s+/gm, "");

// "QĐ 2760/QĐ-BYT (2023) — Hướng dẫn … › IV. ĐIỀU TRỊ › C.1. …" or "…, tr. 54–55"
function parseCitation(citation: string) {
  const [document, ...path] = citation.split(" › ");
  const page = /, tr\. (\d+)/.exec(document);
  return {
    document: page ? document.slice(0, page.index) : document,
    chapter: path.length ? path.join(" › ") : null,
    page: page ? Number(page[1]) : null,
  };
}

type Source = {
  n: number;
  chunk_id?: string;
  kind?: string;
  citation: string;
  text: string;
  stale?: boolean;
};

/** Keeps each source's passage for the source sheet, and returns the citations that point at them. */
export function rememberSources(s: LiveState, sources: Source[]): Citation[] {
  return sources.map((src) => {
    const where = parseCitation(src.citation);
    const id = src.chunk_id ?? `missing-${src.n}`;
    if (src.chunk_id)
      s.passages[id] = {
        ...where,
        text: src.text,
        kind: src.kind ?? null,
        stale: src.stale ?? false,
      };
    return {
      n: src.n,
      passage_id: id,
      document: where.document,
      chapter: where.chapter,
      section: null,
      page: where.page,
      article: null,
    };
  });
}

const KIND_LABEL: Record<string, string> = {
  text: "Đoạn văn",
  table: "Bảng",
  figure: "Hình",
  formula: "Công thức",
};

export function passageView(id: string, p: LiveState["passages"][string]) {
  return {
    id,
    document: p.document,
    chapter: p.chapter,
    section: null,
    page: p.page,
    article: null,
    excerpt: p.text,
    demo_label: (p.kind && KIND_LABEL[p.kind]) ?? "Tài liệu nguồn",
    validity_note: p.stale
      ? "Đoạn nguồn này đã được cập nhật sau khi câu hỏi được viết."
      : null,
  };
}

/** /mcq/answer (or a set report's item): the item with its key, explanations and sources. */
export type AnsweredItem = {
  id: number;
  stem: string;
  lead_in: string;
  options: Record<string, string>;
  van_de: number;
  de_muc: number;
  bloom: string;
  answer: string;
  explanations: Record<
    string,
    { correct: boolean; why: string; mistake?: string }
  >;
  sources: Source[];
  correct: boolean;
  chosen: string | null;
  card?: { event: "added" | "reset" | "reviewed"; text: string } | null;
};

/** The explanation, one rationale per option and the citations; the item is remembered for the tutor. */
export function explain(s: LiveState, r: AnsweredItem) {
  const citations = rememberSources(s, r.sources);
  const explanation = plain(r.explanations[r.answer]?.why ?? "");
  s.questions[String(r.id)] = {
    stem: stemOf(r),
    options: r.options,
    answer: r.answer,
    explanation,
    sources: r.sources.flatMap((x) => (x.chunk_id ? [x.chunk_id] : [])),
  };
  return {
    correct_key: r.answer,
    explanation,
    rationales: Object.fromEntries(
      Object.entries(r.explanations).map(([k, e]) => [
        k,
        plain([e.why, e.mistake].filter(Boolean).join(" ")),
      ]),
    ),
    citations,
  };
}

/** The feedback after one answer. A card is "created" when the answer added it or put it back to day 1. */
export function feedbackOf(s: LiveState, r: AnsweredItem) {
  return {
    correct: r.correct,
    ...explain(s, r),
    card_created: r.card?.event === "added" || r.card?.event === "reset",
    card_note: r.card?.text ?? null,
  };
}
