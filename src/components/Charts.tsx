import type { CurvePoint } from "../lib/api";
import {
  CURVE_FLOOR,
  calendarRows,
  curveGeometry,
  heatLevel,
  share,
} from "../lib/charts";
import { dayMonth, percent } from "../lib/format";

// Small charts for Tiến độ, drawn with plain HTML and SVG. Each one carries its numbers as text too,
// so nothing is said by colour or shape alone.

/** A horizontal bar for a share, with its name on the left and its numbers on the right. */
export function ShareBar({
  label,
  value,
  text,
  color = "var(--primary)",
}: {
  label: string;
  value: number;
  text: string;
  color?: string;
}) {
  return (
    <div>
      <div className="row" style={{ marginBottom: 4 }}>
        <span className="grow">{label}</span>
        <span style={{ fontWeight: 600 }}>{text}</span>
      </div>
      <div className="progress" style={{ height: 8, borderRadius: 4 }}>
        <span style={{ width: `${value * 100}%`, background: color }} />
      </div>
    </div>
  );
}

/** Vertical bars, one per item: the number above, the label under. */
export function Bars({
  items,
  max,
  label,
  color = "var(--primary)",
}: {
  items: { key: string; value: number; caption: string; label: string }[];
  max: number;
  label: string;
  color?: string;
}) {
  return (
    <ol role="list" aria-label={label} className="bars">
      {items.map((item) => (
        <li key={item.key}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>{item.caption}</span>
          <span className="track">
            <span
              style={{
                height: `${share(item.value, max) * 100}%`,
                background: color,
              }}
            />
          </span>
          <span className="muted" style={{ fontSize: 11 }}>
            {item.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

const HEAT = [
  "var(--soft)",
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--primary)",
];
const WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];

/** The last eight weeks, one cell per day, darker for longer study. */
export function Heatmap({
  days,
  label,
}: {
  days: { date: string; minutes: number }[];
  label: string;
}) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      <table className="heat" aria-label={label}>
        <thead>
          <tr>
            {WEEKDAYS.map((d) => (
              <th key={d} scope="col">
                {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {calendarRows(days).map((row, r) => (
            <tr key={r}>
              {row.map((day, c) =>
                day ? (
                  <td
                    key={c}
                    aria-label={`${dayMonth(day.date)}: ${day.minutes} phút`}
                    title={`${dayMonth(day.date)}: ${day.minutes} phút`}
                  >
                    <span
                      style={{ background: HEAT[heatLevel(day.minutes)] }}
                    />
                  </td>
                ) : (
                  <td key={c} />
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <div
        className="row muted"
        style={{ gap: 6, fontSize: 12 }}
        aria-hidden="true"
      >
        Không học
        {HEAT.map((color) => (
          <span
            key={color}
            style={{
              width: 14,
              height: 14,
              borderRadius: 4,
              background: color,
            }}
          />
        ))}
        Trên 75 phút
      </div>
    </div>
  );
}

const W = 300;
const H = 110;

/** One representative card's recall through reviews and seven days without another review. */
export function MemoryCurve({
  points,
  label,
}: {
  points: CurvePoint[];
  label: string;
}) {
  const g = curveGeometry(points, W, H);
  const guide = share(1 - 0.9, 1 - CURVE_FLOOR) * H; // the 90% line
  const reviews = points.filter((p) => p.kind === "review").length;
  const today = [...points].reverse().find((p) => p.kind === "decay");
  const later = points.find((p) => p.kind === "projected");
  const firstReview = points.find((p) => p.kind === "review");
  const todayPosition = g.today ? (g.today.x / W) * 100 : null;
  return (
    <div className="memory-curve stack" style={{ gap: 10 }}>
      <div className="memory-curve-stats">
        <div>
          <span>Hôm nay</span>
          <strong>{percent(today?.recall ?? null)}</strong>
        </div>
        <div>
          <span>Sau 7 ngày</span>
          <strong>{percent(later?.recall ?? null)}</strong>
        </div>
      </div>
      <div className="memory-curve-plot">
        <div className="memory-curve-y-axis" aria-hidden="true">
          <span>100%</span>
          <span>90%</span>
          <span>{percent(CURVE_FLOOR)}</span>
        </div>
        <svg
          role="img"
          aria-label={label + ": thang đo từ " + percent(CURVE_FLOOR) + " đến 100%; " + reviews + " lần ôn; hôm nay " + percent(today?.recall ?? null) + "; sau 7 ngày nếu chưa ôn " + percent(later?.recall ?? null)}
          viewBox="-8 -8 316 126"
          style={{ width: "100%", height: "auto" }}
        >
          <line x1={0} x2={W} y1={0} y2={0} className="memory-curve-grid" />
          <line
            x1={0}
            x2={W}
            y1={guide}
            y2={guide}
            className="memory-curve-guide"
          />
          <line x1={0} x2={W} y1={H} y2={H} className="memory-curve-grid" />
          <path d={g.solid} fill="none" className="memory-curve-solid" />
          {g.dashed && <path d={g.dashed} fill="none" className="memory-curve-projected" />}
          {g.today && (
            <circle
              cx={g.today.x}
              cy={g.today.y}
              r="5"
              className="memory-curve-today"
            />
          )}
        </svg>
      </div>
      <div className="memory-curve-x-axis" aria-hidden="true">
        <span className="start">{firstReview ? dayMonth(firstReview.date) : "Lần ôn"}</span>
        {todayPosition !== null && todayPosition > 12 && todayPosition < 88 && (
          <span className="today" style={{ left: todayPosition + "%" }}>Hôm nay</span>
        )}
        <span className="end">{later ? dayMonth(later.date) : "+7 ngày"}</span>
      </div>
      <div className="memory-curve-legend" aria-hidden="true">
        <span><i className="memory-curve-key solid" /> Đã ôn</span>
        <span><i className="memory-curve-key dashed" /> Nếu chưa ôn</span>
      </div>
      <p className="sr">
        {reviews} lần ôn. Hôm nay độ nhớ khoảng {percent(today?.recall ?? null)}
        {later ? `; sau 7 ngày nếu chưa ôn còn khoảng ${percent(later.recall)}.` : "."}
      </p>
    </div>
  );
}

/** Missing axes have no mark or connecting edge, rather than an invented zero. */
export function AssessmentRadar({
  axes,
  label,
}: {
  axes: { id: string; label: string; correct: number; total: number }[];
  label: string;
}) {
  const center = { x: 210, y: 178 };
  const radius = 108;
  const point = (i: number, distance: number) => {
    const angle = (i * Math.PI * 2) / axes.length - Math.PI / 2;
    return {
      x: center.x + Math.cos(angle) * distance,
      y: center.y + Math.sin(angle) * distance,
    };
  };
  const points = (distance: number) =>
    axes
      .map((_, i) => {
        const p = point(i, distance);
        return `${p.x},${p.y}`;
      })
      .join(" ");
  const allAssessed = axes.length >= 3 && axes.every((a) => a.total > 0);
  const assessedPoint = (i: number) =>
    point(i, radius * share(axes[i].correct, axes[i].total));
  return (
    <figure className="assessment-radar">
      <svg viewBox="0 0 420 356" role="img" aria-label={label}>
        {[0.25, 0.5, 0.75, 1].map((scale) => (
          <polygon
            key={scale}
            points={points(radius * scale)}
            fill="none"
            stroke="var(--border-input)"
            strokeWidth="1"
          />
        ))}
        {axes.map((axis, i) => {
          const end = point(i, radius);
          const name = point(i, radius + 42);
          const pct = axis.total
            ? `${Math.round(share(axis.correct, axis.total) * 100)}%`
            : "—";
          return (
            <g key={axis.id}>
              <line
                x1={center.x}
                y1={center.y}
                x2={end.x}
                y2={end.y}
                stroke="var(--border-input)"
              />
              <text
                x={name.x}
                y={name.y - 2}
                textAnchor="middle"
                className="radar-axis-label"
              >
                {axis.label}
              </text>
              <text
                x={name.x}
                y={name.y + 16}
                textAnchor="middle"
                className="radar-axis-value"
              >
                {pct}
              </text>
            </g>
          );
        })}
        {allAssessed && (
          <polygon
            points={axes
              .map((_, i) => {
                const p = assessedPoint(i);
                return `${p.x},${p.y}`;
              })
              .join(" ")}
            fill="var(--primary-tint)"
            stroke="var(--primary)"
            strokeWidth="2"
          />
        )}
        {!allAssessed &&
          axes.map((a, i) => {
            const next = (i + 1) % axes.length;
            if (!a.total || !axes[next].total) return null;
            const from = assessedPoint(i),
              to = assessedPoint(next);
            return (
              <line
                key={a.id}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="var(--primary)"
                strokeWidth="2"
              />
            );
          })}
        {axes.map((axis, i) => {
          if (!axis.total) return null;
          const p = assessedPoint(i);
          return (
            <circle
              key={axis.id}
              cx={p.x}
              cy={p.y}
              r="4.5"
              fill="var(--primary)"
              stroke="white"
              strokeWidth="2"
            >
              <title>
                {axis.label}: {axis.correct}/{axis.total} câu đúng
              </title>
            </circle>
          );
        })}
        <text x={center.x + 6} y={center.y - 6} className="radar-scale">
          0
        </text>
        <text
          x={center.x + 6}
          y={center.y - radius * 0.5 - 5}
          className="radar-scale"
        >
          50
        </text>
        <text
          x={center.x + 6}
          y={center.y - radius - 5}
          className="radar-scale"
        >
          100%
        </text>
      </svg>
      <figcaption>
        Tỷ lệ câu đúng · Thang 0–100%. Trục “—” chưa có dữ liệu.
      </figcaption>
    </figure>
  );
}
