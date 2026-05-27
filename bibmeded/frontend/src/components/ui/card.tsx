import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  as?: "div" | "section" | "article";
  elevation?: 1 | 2 | 3;
  padding?: "none" | "sm" | "md" | "lg";
  interactive?: boolean;
  children?: ReactNode;
}

const PADDING: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "",
  sm: "p-4",
  md: "p-6",
  lg: "p-8 md:p-10",
};

export function Card({
  as: Tag = "div",
  elevation = 1,
  padding = "md",
  interactive = false,
  className = "",
  children,
  ...rest
}: CardProps) {
  const elevClass = elevation === 1 ? "elev-1" : elevation === 2 ? "elev-2" : "elev-3";
  return (
    <Tag
      className={[
        "bg-surface-raised rounded-[var(--radius-lg)]",
        "border border-divider",
        elevClass,
        PADDING[padding],
        interactive
          ? "transition-shadow duration-[var(--duration-base)] ease-[var(--ease-standard)] hover:elev-2 cursor-pointer"
          : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  className = "",
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-start justify-between gap-6 mb-6 ${className}`}>
      <div className="min-w-0">
        <h2
          className="text-2xl font-bold text-primary leading-tight"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {title}
        </h2>
        {subtitle ? (
          <p className="mt-1 text-sm text-on-surface-muted leading-relaxed">{subtitle}</p>
        ) : null}
      </div>
      {action ? <div className="flex-shrink-0">{action}</div> : null}
    </div>
  );
}
