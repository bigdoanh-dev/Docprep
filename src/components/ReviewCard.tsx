import { SaveQuestion } from "./SaveQuestion";
import { motion } from "motion/react";
import { useState } from "react";
import type { Citation, DueCard } from "../lib/api";
import { SourceSheet } from "./Answer";
import { Icon } from "./Icon";
import { Sheet } from "./Sheet";

export type Rating = "1" | "2" | "3" | "4";
// The one place the rating labels are written (open issue 33: the mocks disagree on them).
export const RATINGS: {
  rating: Rating;
  label: string;
  style: React.CSSProperties;
}[] = [
  {
    rating: "1",
    label: "Học lại",
    style: {
      background: "var(--warn-bg)",
      borderColor: "#e8c58f",
      color: "var(--warn-text)",
    },
  },
  {
    rating: "2",
    label: "Khó",
    style: {
      background: "var(--surface)",
      borderColor: "var(--border-input)",
      color: "var(--ink)",
    },
  },
  {
    rating: "3",
    label: "Tốt",
    style: {
      background: "var(--primary-tint)",
      borderColor: "var(--primary)",
      color: "var(--primary-dark)",
      borderWidth: 2,
    },
  },
  {
    rating: "4",
    label: "Dễ",
    style: {
      background: "var(--new-tint)",
      borderColor: "#b5cbe8",
      color: "var(--new)",
    },
  },
];

// One revision card, in the session and in deck mode alike. The source and the reason are there but
// collapsed (handover/06-screens.md, rule 6). The caller gives the card as `key`, so what was opened
// on one card is closed on the next.
export function ReviewCard({
  card,
  revealed,
  prompt,
  onSuspend,
  busy,
}: {
  card: DueCard;
  revealed: boolean;
  prompt?: string; // a line under the front until the card is turned
  onSuspend: () => void;
  busy: boolean;
}) {
  const [sourceOpen, setSourceOpen] = useState(false);
  const [whyOpen, setWhyOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [passage, setPassage] = useState<Citation | null>(null);

  const citation: Citation = {
    n: 1,
    passage_id: card.source_passage_id,
    document: card.citation,
    chapter: null,
    section: null,
    page: null,
    article: null,
  };
  return (
    <div className="card stack" style={{ padding: 20, minHeight: 320 }}>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <span className="label grow" style={{ fontSize: 12, paddingTop: 12 }}>
          {card.module}
        </span>
        <button
          className="icon-btn"
          aria-label="Tuỳ chọn thẻ"
          onClick={() => setMenuOpen(true)}
          disabled={busy}
        >
          <Icon name="more" />
        </button>
      </div>
      <h2 className="title" style={{ fontSize: 20 }}>
        {card.front}
      </h2>
      <SaveQuestion
        id={`card:${card.id}`}
        title={card.front}
        detail={revealed ? card.back : undefined}
        source={card.citation}
      />
      {!revealed && prompt && <p className="muted">{prompt}</p>}
      {revealed && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
          className="stack"
          style={{
            borderTop: "1px dashed var(--border-input)",
            paddingTop: 16,
          }}
          aria-live="polite"
        >
          {card.back.split("\n\n").map((para, i) => (
            <p
              key={i}
              className="reading"
              style={i === 0 ? { fontWeight: 500 } : undefined}
            >
              {para}
            </p>
          ))}
          <div className="row" style={{ gap: 20, flexWrap: "wrap" }}>
            <button
              className="textlink"
              aria-expanded={sourceOpen}
              onClick={() => setSourceOpen(!sourceOpen)}
            >
              Nguồn
            </button>
            <button
              className="textlink"
              aria-expanded={whyOpen}
              onClick={() => setWhyOpen(!whyOpen)}
            >
              Vì sao ôn câu này?
            </button>
          </div>
          {sourceOpen && (
            <div>
              <button className="chip" onClick={() => setPassage(citation)}>
                {card.citation}
              </button>
            </div>
          )}
          {whyOpen && (
            <p className="note">
              Bạn đã trả lời sai câu này.{" "}
              <span className="tag">{card.origin}</span>
            </p>
          )}
        </motion.div>
      )}
      <Sheet
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        title="Tuỳ chọn thẻ"
      >
        <div className="stack">
          <p className="muted small">
            Thẻ tạm ẩn không xuất hiện trong các lượt ôn cho đến khi bạn mở lại.
          </p>
          <button
            className="btn block"
            onClick={() => {
              setMenuOpen(false);
              onSuspend();
            }}
          >
            Tạm ẩn thẻ này
          </button>
        </div>
      </Sheet>
      <SourceSheet citation={passage} onClose={() => setPassage(null)} />
    </div>
  );
}

// The footer under a card: turn it, then say how well it was remembered.
export function ReviewActions({
  revealed,
  revealLabel,
  onReveal,
  onRate,
  busy,
  sent = null,
}: {
  revealed: boolean;
  revealLabel: string;
  onReveal: () => void;
  onRate: (rating: Rating) => void;
  busy: boolean;
  // The rating already sent for this card. If its reply was lost the server may still hold it, and a
  // retry is answered with what was stored: so only that rating can be sent again.
  sent?: Rating | null;
}) {
  return (
    <footer className="footer" style={{ gap: 8 }}>
      {!revealed ? (
        <button className="btn primary lg block" onClick={onReveal}>
          {revealLabel}
        </button>
      ) : (
        RATINGS.map(({ rating, label, style }) => (
          <button
            key={rating}
            className="grow"
            onClick={() => onRate(rating)}
            disabled={busy || (sent !== null && sent !== rating)}
            style={{
              minHeight: 60,
              borderRadius: 14,
              borderStyle: "solid",
              borderWidth: 1,
              padding: "6px 2px",
              ...style,
            }}
          >
            <span style={{ display: "block", fontWeight: 600 }}>{label}</span>
          </button>
        ))
      )}
    </footer>
  );
}
