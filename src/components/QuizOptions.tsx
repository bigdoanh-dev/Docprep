import { Check, X } from "lucide-react";
import { motion } from "motion/react";
import type { Option } from "../lib/api";

const LETTERS = ["A", "B", "C", "D", "E", "F"];

// The options of a multiple-choice question, in a unit and in a practice set. Before the answer the
// learner picks one; after checking, navy marks the correct answer and amber marks a wrong pick.
export function QuizOptions({
  options,
  picked,
  correctKey,
  disabled,
  onPick,
}: {
  options: Option[];
  picked: string | null;
  correctKey: string | null; // null until the answer has been checked
  disabled: boolean;
  onPick: (key: string) => void;
}) {
  const short = options.every((o) => o.text.length <= 12);
  return (
    <div
      role="radiogroup"
      aria-label="Các phương án"
      className="quiz-options-grid"
      style={{
        display: "grid",
        gridTemplateColumns: short ? "repeat(2, minmax(0, 1fr))" : "1fr",
        gap: 12,
      }}
    >
      {options.map((o, idx) => {
        const chosen = picked === o.key;
        const isCorrect = correctKey === o.key;
        const isWrongPick = correctKey !== null && chosen && !isCorrect;
        const letter = LETTERS[idx] || String.fromCharCode(65 + idx);
        const style = isCorrect
          ? {
              background: "var(--primary-tint)",
              borderColor: "var(--primary)",
              boxShadow: "0 0 0 1px var(--primary)",
            }
          : isWrongPick
            ? {
                background: "var(--learning-tint)",
                borderColor: "var(--learning)",
                boxShadow: "0 0 0 1px var(--learning)",
              }
            : chosen
              ? {
                  background: "var(--primary-tint)",
                  borderColor: "var(--primary)",
                  boxShadow: "0 0 0 1px var(--primary)",
                }
              : {
                  background: "#ffffff",
                  borderColor: "var(--border-input)",
                };
        return (
          <motion.button
            whileTap={{ scale: 0.995 }}
            animate={{
              boxShadow: isCorrect ? "0 0 0 3px rgba(40, 88, 165, 0.14)" : "none",
            }}
            key={o.key}
            role="radio"
            aria-checked={chosen}
            disabled={disabled || correctKey !== null}
            onClick={() => onPick(o.key)}
            className={`quiz-option-button ${chosen ? "chosen" : ""} ${isCorrect ? "correct" : ""} ${isWrongPick ? "wrong" : ""}`}
            style={{
              ...style,
              minHeight: 56,
              borderRadius: 12,
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              gap: 12,
              borderWidth: 1.5,
              borderStyle: "solid",
              fontSize: short ? 16 : 14.5,
              fontWeight: 500,
              color: "var(--ink)",
              opacity: 1,
              textAlign: "left",
              cursor: disabled || correctKey !== null ? "default" : "pointer",
            }}
          >
            <span
              className="quiz-option-badge"
              style={{
                width: 28,
                height: 28,
                borderRadius: 7,
                fontSize: 13,
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                background: isCorrect
                  ? "var(--primary)"
                  : isWrongPick
                    ? "var(--learning)"
                    : chosen
                      ? "var(--primary)"
                      : "var(--soft)",
                color: isCorrect || isWrongPick || chosen ? "#ffffff" : "var(--muted)",
                transition: "all 0.15s ease",
              }}
            >
              {letter}
            </span>
            <span style={{ flex: 1, lineHeight: 1.45 }}>{o.text}</span>
            {isCorrect && (
              <span
                style={{
                  color: "var(--primary)",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  flexShrink: 0,
                }}
              >
                <Check size={18} />
                <span className="sr">đáp án đúng</span>
              </span>
            )}
            {isWrongPick && (
              <span
                style={{
                  color: "var(--learning-dark)",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  flexShrink: 0,
                }}
              >
                <X size={18} />
                <span className="sr">bạn chọn, chưa đúng</span>
              </span>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}
