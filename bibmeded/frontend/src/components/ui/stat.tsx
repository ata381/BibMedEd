import type { ReactNode } from "react";

interface StatProps {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  size?: "md" | "lg";
  tone?: "default" | "primary" | "accent" | "danger" | "warning";
  className?: string;
}

const TONE: Record<NonNullable<StatProps["tone"]>, string> = {
  default: "text-on-surface",
  primary: "text-primary",
  accent: "text-accent",
  danger: "text-danger",
  warning: "text-warning",
};

// A single figure the way a journal table sets it: small-caps label above a
// large serif numeral, with an optional footnote. Compose several inside a
// <StatRow> to get a ruled, table-like strip instead of a pile of cards.
export function Stat({ label, value, note, size = "md", tone = "default", className = "" }: StatProps) {
  return (
    <div className={`min-w-0 ${className}`}>
      <p className="eyebrow">{label}</p>
      <p className={`numeral mt-2 ${size === "lg" ? "text-4xl md:text-5xl" : "text-3xl md:text-4xl"} ${TONE[tone]}`}>{value}</p>
      {note ? <p className="mt-2 text-xs text-on-surface-subtle leading-snug">{note}</p> : null}
    </div>
  );
}

export function StatRow({ children, className = "", ariaLabel }: { children: ReactNode; className?: string; ariaLabel?: string }) {
  return (
    <div
      role={ariaLabel ? "group" : undefined}
      aria-label={ariaLabel}
      className={[
        "grid grid-cols-2 md:grid-cols-4 rule-t rule-b",
        "[&>*]:py-5 [&>*]:px-4 md:[&>*]:px-6 [&>*:first-child]:pl-0 md:[&>*:last-child]:pr-0",
        "[&>*+*]:border-l [&>*+*]:border-divider max-md:[&>*:nth-child(odd)]:border-l-0 max-md:[&>*:nth-child(n+3)]:border-t max-md:[&>*:nth-child(n+3)]:border-divider",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}
