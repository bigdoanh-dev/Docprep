import { type SVGProps } from "react";
import { Link } from "react-router-dom";

export function BrandMark({
  size = 32,
  className = "",
  ...props
}: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`brand-mark ${className}`}
      aria-hidden="true"
      {...props}
    >
      {/* Outer Academic Medical Shield - Solid Institutional Navy */}
      <path
        d="M24 3.5L39 9V22.5C39 32.8 32.5 40.8 24 44.5C15.5 40.8 9 32.8 9 22.5V9L24 3.5Z"
        fill="#0a2540"
      />

      {/* Inner Shield Body - Deep Sapphire Contrast */}
      <path
        d="M24 6L36.5 10.8V22C36.5 30.8 31 37.8 24 41C17 37.8 11.5 30.8 11.5 22V10.8L24 6Z"
        fill="#0f375f"
        stroke="#14b8a6"
        strokeWidth="0.8"
        strokeOpacity="0.45"
      />

      {/* Precision Medical Cross - Solid Pure White */}
      <rect x="21" y="13" width="6" height="22" rx="1.5" fill="#ffffff" />
      <rect x="13" y="21" width="22" height="6" rx="1.5" fill="#ffffff" />

      {/* Rod of Asclepius Staff - Golden Bronze */}
      <line
        x1="24"
        y1="10"
        x2="24"
        y2="36"
        stroke="#d97706"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="24" cy="9.5" r="1.8" fill="#d97706" />

      {/* Sacred Serpent of Medicine - Emerald Teal Coiling Naturally */}
      <path
        d="M26.8 13.8C26.8 12.4 24.2 12.2 22.6 13.6C21 15.2 22 17.8 24 18.8C26.5 20.1 27 22.6 25.2 24.2C23.5 25.8 21.6 25.8 21.6 27.2C21.6 28.8 24.2 29.8 25.8 31.2C27.2 32.6 25.8 34.5 23.5 34.5"
        fill="none"
        stroke="#0d9488"
        strokeWidth="1.8"
        strokeLinecap="round"
      />

      {/* Open Medical Codex (Education & Clinical Practice Book at Base) */}
      <path
        d="M16.5 37.5C19 36.2 21.6 36.4 24 37.8C26.4 36.4 29 36.2 31.5 37.5V39.2C29 37.8 26.4 38 24 39.5C21.6 38 19 37.8 16.5 39.2V37.5Z"
        fill="#e2e8f0"
      />
    </svg>
  );
}

export function BrandLogo({
  to = "/gioi-thieu",
  subtitle = "Hỗ trợ ôn thi bác sĩ Y học dự phòng",
  theme = "default",
  compact = false,
  size = 36,
}: {
  to?: string;
  subtitle?: string;
  theme?: "default" | "light" | "sidebar";
  compact?: boolean;
  size?: number;
}) {
  const content = (
    <div className={`brand-identity theme-${theme} ${compact ? "compact" : ""}`}>
      <BrandMark size={size} />
      <div className="brand-text">
        <span className="brand-name">
          <strong className="brand-accent">DocPrep</strong>
          <span className="brand-badge-pill">YHDP</span>
        </span>
        {subtitle && !compact && <span className="brand-subtitle">{subtitle}</span>}
      </div>
    </div>
  );

  if (!to) return content;
  return (
    <Link to={to} className="brand-link" aria-label="DocPrep YHDP - Trang chủ">
      {content}
    </Link>
  );
}
