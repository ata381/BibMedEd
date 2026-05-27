import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon = "inbox",
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`text-center py-16 px-6 ${className}`}>
      <div
        aria-hidden="true"
        className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-surface-sunken text-on-surface-subtle mb-4"
      >
        <span className="material-symbols-outlined" style={{ fontSize: "32px" }}>
          {icon}
        </span>
      </div>
      <h3
        className="text-xl font-bold text-on-surface"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {title}
      </h3>
      {description ? (
        <p className="mt-2 max-w-md mx-auto text-sm text-on-surface-muted leading-relaxed">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
