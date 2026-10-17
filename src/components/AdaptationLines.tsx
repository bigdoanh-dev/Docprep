import { adaptationLines, type AdaptationSummary } from "../lib/adaptation";
import { Icon } from "./Icon";

// What a finished practice set changed, one line per thing the server reported. `shown` limits the
// list to its first lines while the adapting screen reveals them one after another.
export function AdaptationLines({
  summary,
  shown,
  onDark = false,
}: {
  summary: AdaptationSummary;
  shown?: number;
  onDark?: boolean;
}) {
  const lines = adaptationLines(summary).slice(0, shown);
  return (
    <ul
      style={{ listStyle: "none", margin: 0, padding: 0 }}
      className="stack"
      aria-live="polite"
    >
      {lines.map((line) => (
        <li key={line.label} className="row" style={{ minHeight: 44 }}>
          <span
            style={{
              color: onDark ? "var(--primary-on-dark)" : "var(--primary-dark)",
              display: "flex",
            }}
          >
            <Icon name="check" size={20} />
          </span>
          <span className="grow">{line.label}</span>
          <span style={{ fontWeight: 600, textAlign: "right" }}>
            {line.result}
          </span>
        </li>
      ))}
    </ul>
  );
}
