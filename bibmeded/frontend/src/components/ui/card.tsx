import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "section" | "article" | "aside";
  elevation?: 0 | 1 | 2 | 3;
  padding?: "none" | "sm" | "md" | "lg";
  interactive?: boolean;
  tone?: "raised" | "sunken" | "ink";
  children?: ReactNode;
}

const PADDING: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "",
  sm: "p-4",
  md: "p-5 md:p-6",
  lg: "p-6 md:p-8",
};

const ELEVATION = ["", "elev-1", "elev-2", "elev-3"];

const TONE: Record<NonNullable<CardProps["tone"]>, string> = {
  raised: "bg-surface-raised border border-divider",
  sunken: "bg-surface-sunken border border-transparent",
  ink: "bg-ink text-on-ink border border-transparent",
};

export function Card({
  as: Tag = "div",
  elevation = 0,
  padding = "md",
  interactive = false,
  tone = "raised",
  className = "",
  children,
  ...rest
}: CardProps) {
  return (
    <Tag
      className={[
        "rounded-[var(--radius-lg)]",
        TONE[tone],
        ELEVATION[elevation],
        PADDING[padding],
        interactive
          ? "transition-[border-color,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-standard)] hover:border-outline-strong hover:elev-2"
          : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </Tag>
  );
}

interface CardHeaderProps {
  title: ReactNode;
  eyebrow?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  as?: "h2" | "h3";
  className?: string;
}

export function CardHeader({ title, eyebrow, subtitle, action, as: Heading = "h2", className = "" }: CardHeaderProps) {
  return (
    <div className={`flex items-start justify-between gap-6 mb-5 ${className}`}>
      <div className="min-w-0">
        {eyebrow ? <p className="eyebrow mb-1.5">{eyebrow}</p> : null}
        <Heading className="text-xl md:text-2xl text-on-surface leading-tight">{title}</Heading>
        {subtitle ? <p className="mt-1.5 text-sm text-on-surface-muted leading-relaxed max-w-prose">{subtitle}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
