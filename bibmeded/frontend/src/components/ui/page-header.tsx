import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  lede?: ReactNode;
  aside?: ReactNode;
  children?: ReactNode;
  size?: "md" | "lg";
  className?: string;
}

// Editorial page opener: eyebrow, serif headline, one-paragraph lede, and an
// optional right-hand column for metadata or a primary action. The bottom
// rule anchors the page so content below reads as body copy.
export function PageHeader({ eyebrow, title, lede, aside, children, size = "md", className = "" }: PageHeaderProps) {
  const titleSize = size === "lg" ? "text-4xl md:text-5xl" : "text-3xl md:text-4xl";
  return (
    <header className={`pt-2 pb-6 md:pb-8 rule-b ${className}`}>
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
        <div className="min-w-0 max-w-3xl">
          {eyebrow ? <p className="eyebrow mb-3">{eyebrow}</p> : null}
          <h1 className={`${titleSize} text-on-surface leading-[1.05]`}>{title}</h1>
          {lede ? <p className="mt-4 text-base md:text-lg text-on-surface-muted leading-relaxed max-w-2xl">{lede}</p> : null}
        </div>
        {aside ? <div className="shrink-0 md:text-right">{aside}</div> : null}
      </div>
      {children ? <div className="mt-6">{children}</div> : null}
    </header>
  );
}
