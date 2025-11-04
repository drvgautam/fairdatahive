interface LogoProps {
  size?: number | string;
  className?: string;
  title?: string;
}

/** Same mark as docs/assets/logo.svg and the browser tab favicon. */
export function Logo({
  size = 32,
  className,
  title = "FairDataHive",
}: LogoProps) {
  return (
    <svg
      viewBox="0 0 40 40"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={title}
      width={size}
      height={size}
      className={className ? `logo-mark ${className}` : "logo-mark"}
    >
      <title>{title}</title>
      <rect className="logo-bg" width="40" height="40" rx="8" />
      <polygon
        className="logo-frame"
        points="20,3 34.64,11.5 34.64,28.5 20,37 5.36,28.5 5.36,11.5"
        strokeLinejoin="round"
      />
      <g className="logo-inner" strokeWidth="1.4" strokeLinecap="round">
        <line x1="13.5" y1="15" x2="26.5" y2="15" />
        <line x1="13.5" y1="15" x2="20" y2="27" />
        <line x1="26.5" y1="15" x2="20" y2="27" />
      </g>
      <g className="logo-dots">
        <circle className="logo-dot" cx="13.5" cy="15" r="2.6" />
        <circle className="logo-dot" cx="26.5" cy="15" r="2.6" />
        <circle className="logo-dot" cx="20" cy="27" r="2.6" />
      </g>
    </svg>
  );
}
