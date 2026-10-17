import React from "react";

interface WaveDividerProps {
  /** The primary fill color that blends into the adjacent section */
  fillColor?: string;
  /** Optional secondary accent wave color for subtle depth */
  accentColor?: string;
  /** Custom extra CSS classes */
  className?: string;
  /** Flip horizontally or vertically if needed */
  flipX?: boolean;
  flipY?: boolean;
  /** Optional carousel indicator dots in the curve trough */
  showDots?: boolean;
}

/**
 * WaveDivider creates an organic, smooth Bézier wave transition between sections,
 * matching the flowing organic wave from the user reference photo.
 */
export const WaveDivider: React.FC<WaveDividerProps> = ({
  fillColor = "var(--hero-wave-fill, #ffffff)",
  accentColor,
  className = "",
  flipX = false,
  flipY = false,
  showDots = false,
}) => {
  const transform = [
    flipX ? "scaleX(-1)" : "",
    flipY ? "scaleY(-1)" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={`hero-wave-divider ${className}`}
      aria-hidden="true"
      style={transform ? { transform } : undefined}
    >
      <svg
        viewBox="0 0 1440 160"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="none"
        className="hero-wave-svg"
      >
        {/* Optional secondary accent layer (only rendered if explicitly provided) */}
        {accentColor && (
          <path
            d="M 0,95 C 160,30 300,26 440,40 C 580,54 640,118 740,118 C 860,118 1160,45 1440,32 L 1440,160 L 0,160 Z"
            fill={accentColor}
          />
        )}
        {/* Main solid white Bézier wave matching user reference photo:
            - Starts at y=85 on the left
            - Smoothly crests up to y=24 around x=320
            - Gently dips down to y=110 at x=740 (where indicator dots sit)
            - Sweeps elegantly up to y=25 at the right edge
            - Completely solid white fill masking the bottom of the hero */}
        <path
          d="M 0,85 C 160,20 300,18 440,32 C 580,46 640,110 740,110 C 840,110 1160,35 1440,25 L 1440,160 L 0,160 Z"
          fill={fillColor}
        />
        {/* Carousel indicator dots in the curve trough matching user reference */}
        {showDots && (
          <g className="wave-indicator-dots" transform="translate(740, 108)">
            <circle cx="-10" cy="0" r="7.5" fill="#38bdf8" fillOpacity="0.25" />
            <circle cx="-10" cy="0" r="4.5" fill="#0284c7" />
            <circle cx="8" cy="0" r="3.5" fill="#94a3b8" />
          </g>
        )}
      </svg>
    </div>
  );
};
