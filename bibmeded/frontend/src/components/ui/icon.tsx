import type { SVGProps } from "react";

// Inline stroke icons (24-unit grid, geometry in the style of Lucide, ISC).
// Bundled with the app so the UI renders identically offline and inside the
// e2e harness — no runtime request to an icon-font CDN.
const PATHS = {
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4.3-4.3",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  chart: "M3 3v18h18M7 15v-4M12 15V7M17 15v-6",
  download: "M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
  folder: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z",
  plus: "M12 5v14M5 12h14",
  flask: "M9 3h6M10 3v6L4.5 18.5A2 2 0 0 0 6.3 21h11.4a2 2 0 0 0 1.8-2.5L14 9V3M7 15h10",
  trash: "M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 10v7M14 10v7",
  external: "M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5",
  book: "M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5a2.5 2.5 0 0 0 0 5H20M4 4.5v17A2.5 2.5 0 0 0 6.5 24",
  github: "M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21",
  sun: "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  moon: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z",
  contrast: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 0v18a9 9 0 0 0 0-18Z",
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5 9.5 17 19 7",
  checkCircle: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm-3.5 9 2.5 2.5 4.5-5",
  xCircle: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM9 9l6 6M15 9l-6 6",
  alert: "M12 9v4m0 4h.01M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 5h.01M12 11v5",
  arrowRight: "M5 12h14m-6-6 6 6-6 6",
  arrowLeft: "M19 12H5m6 6-6-6 6-6",
  chevronLeft: "M15 6l-6 6 6 6",
  chevronRight: "M9 6l6 6-6 6",
  network: "M12 3a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5ZM5 16a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Zm14 0a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5ZM12 8v4m0 0-5.5 4.5M12 12l5.5 4.5",
  tag: "M3 12V4h8l9 9-8 8-9-9Zm4-5h.01",
  quote: "M6 10c0-2 1.3-3.5 3-4M4 14a3 3 0 1 0 6 0v-3H5m9-1c0-2 1.3-3.5 3-4m-3 8a3 3 0 1 0 6 0v-3h-5",
  users: "M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm13 17v-2a4 4 0 0 0-3-3.9M15 3.1a4 4 0 0 1 0 7.8",
  fileText: "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8M8 17h6",
  table: "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5Zm0 4h18M3 15h18M9 3v18",
  archive: "M3 4h18v5H3V4Zm1 5v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9M10 13h4",
  terminal: "M4 17l6-5-6-5M12 19h8",
  sliders: "M4 21v-7m0-4V3m8 18v-9m0-4V3m8 18v-5m0-4V3M1 14h6M9 8h6m2 8h6",
  filter: "M3 4h18l-7 9v6l-4 2v-8L3 4Z",
  sparkles: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3ZM5 19l.7 1.8L7.5 21.5l-1.8.7L5 24l-.7-1.8L2.5 21.5l1.8-.7L5 19Z",
  calendar: "M8 2v3m8-3v3M3 9h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z",
  loader: "M12 3v3m6.4-.4-2.1 2.1M21 12h-3m-.6 6.4-2.1-2.1M12 21v-3m-6.4.4 2.1-2.1M3 12h3m.6-6.4 2.1 2.1",
  zoomIn: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4.3-4.3M11 8v6M8 11h6",
  zoomOut: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4.3-4.3M8 11h6",
  fit: "M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3",
  flow: "M6 3v6m0 0a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm0 6v6M18 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm0 6c0 4-2 6-6 6H9",
  rule: "M3 5h18M3 12h12M3 19h18",
  inbox: "M22 12h-6l-2 3h-4l-2-3H2m20 0v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6m20 0-3.5-7H5.5L2 12",
  searchOff: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4.3-4.3M8.5 8.5l5 5m0-5-5 5",
  refresh: "M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
  eyeOff: "M3 3l18 18M10.6 5.2A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.4 4.2M6.6 6.6A16 16 0 0 0 2 12s3.5 7 10 7c1.5 0 2.9-.4 4.1-1M9.9 9.9a3 3 0 0 0 4.2 4.2",
  layers: "M12 3 2 8l10 5 10-5-10-5ZM2 13l10 5 10-5M2 18l10 5 10-5",
  globe: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 0c-2.5 2.5-3.5 5.5-3.5 9s1 6.5 3.5 9c2.5-2.5 3.5-5.5 3.5-9S14.5 5.5 12 3ZM3 12h18",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3Z",
  home: "M3 11l9-8 9 8v9a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2v-9Z",
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  size?: number | string;
  label?: string;
  strokeWidth?: number;
}

export function Icon({ name, size = 20, label, strokeWidth = 1.75, className = "", ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      className={`shrink-0 ${className}`}
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
