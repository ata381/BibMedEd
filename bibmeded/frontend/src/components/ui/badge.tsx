import type { ReactNode } from "react";

type Tone = "neutral" | "primary" | "accent" | "success" | "warning" | "danger" | "info" | "ink";

interface BadgeProps {
  tone?: Tone;
  size?: "sm" | "md";
  children: ReactNode;
  className?: string;
}

const TONE: Record<Tone, string> = {
  neutral: "bg-surface-sunken text-on-surface-muted border-divider",
  primary: "bg-primary-container text-on-primary-container border-transparent",
  accent: "bg-accent-container text-on-accent-container border-transparent",
  success: "bg-success-container text-on-accent-container border-transparent",
  warning: "bg-warning-container text-warning border-transparent",
  danger: "bg-danger-container text-danger border-transparent",
  info: "bg-info-container text-on-primary-container border-transparent",
  ink: "bg-ink text-on-ink border-transparent",
};

export function Badge({ tone = "neutral", size = "sm", children, className = "" }: BadgeProps) {
  const sizeClass = size === "sm" ? "h-5 px-1.5 text-2xs" : "h-6 px-2 text-xs";
  return (
    <span
      className={[
        "inline-flex items-center gap-1 font-bold tracking-[0.1em] uppercase border rounded-[var(--radius-sm)] whitespace-nowrap",
        sizeClass,
        TONE[tone],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}
