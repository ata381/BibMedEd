import type { ReactNode } from "react";
import { Icon, type IconName } from "./icon";

interface EmptyStateProps {
  icon?: IconName;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon = "inbox", title, description, action, className = "" }: EmptyStateProps) {
  return (
    <div className={`text-center py-14 px-6 ${className}`}>
      <div className="inline-flex items-center justify-center w-14 h-14 rounded-full border border-divider bg-surface text-on-surface-subtle mb-4">
        <Icon name={icon} size={26} />
      </div>
      <h3 className="text-xl text-on-surface">{title}</h3>
      {description ? (
        <p className="mt-2 max-w-md mx-auto text-sm text-on-surface-muted leading-relaxed">{description}</p>
      ) : null}
      {action ? <div className="mt-6 flex justify-center">{action}</div> : null}
    </div>
  );
}
