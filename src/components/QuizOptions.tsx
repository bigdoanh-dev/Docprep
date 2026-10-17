import { Check, X } from "lucide-react";
import { motion } from "motion/react";
import type { Option } from "../lib/api";

const LETTERS = ["A", "B", "C", "D", "E", "F"];

// The options of a multiple-choice question, in a unit and in a practice set. Before the answer the
// learner picks one; after it the correct one is green and a wrong pick orange (never red).
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
              background: "#ecfdf5",
              borderColor: "#10b981",
              boxShadow: "0 0 0 1px #10b981",
            }
          : isWrongPick
            ? {
                background: "#fff7ed",
                borderColor: "#f97316",
                boxShadow: "0 0 0 1px #f97316",
              }
            : chosen
              ? {
                  background: "#f0f9ff",
                  borderColor: "var(--primary)",
                  boxShadow: "0 0 0 1px var(--primary)",
                }
              : {
                  background: "#ffffff",
                  borderColor: "#cbd5e1",
                };
        return (
          <motion.button
            whileTap={{ scale: 0.995 }}
            animate={{
              boxShadow: isCorrect ? "0 0 0 3px rgba(16, 185, 129, 0.15)" : "none",
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
                  ? "#10b981"
                  : isWrongPick
                    ? "#f97316"
                    : chosen
                      ? "var(--primary)"
                      : "#f1f5f9",
                color: isCorrect || isWrongPick || chosen ? "#ffffff" : "#475569",
                transition: "all 0.15s ease",
              }}
            >
              {letter}
            </span>
            <span style={{ flex: 1, lineHeight: 1.45 }}>{o.text}</span>
            {isCorrect && (
              <span
                style={{
                  color: "#059669",
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
                  color: "#ea580c",
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
