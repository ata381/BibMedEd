import type { ReactNode } from "react";

type Tone = "neutral" | "primary" | "success" | "warning" | "danger" | "info";

interface BadgeProps {
  tone?: Tone;
  size?: "sm" | "md";
  children: ReactNode;
  className?: string;
}

const TONE: Record<Tone, string> = {
  neutral: "bg-surface-sunken text-on-surface-muted",
  primary: "bg-primary-container text-on-primary-container",
  success: "bg-success-container text-success",
  warning: "bg-warning-container text-warning",
  danger: "bg-danger-container text-danger",
  info: "bg-info-container text-info",
};

export function Badge({ tone = "neutral", size = "sm", children, className = "" }: BadgeProps) {
  const sizeClass = size === "sm" ? "h-5 px-2 text-[11px]" : "h-6 px-2.5 text-xs";
  return (
    <span
      className={[
        "inline-flex items-center font-bold tracking-wide uppercase rounded-[var(--radius-pill)]",
        sizeClass,
        TONE[tone],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}
