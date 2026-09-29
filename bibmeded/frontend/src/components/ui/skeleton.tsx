import type { ReactNode } from "react";

interface SkeletonProps {
  className?: string;
  rounded?: "sm" | "md" | "lg" | "pill" | "full";
}

const ROUNDED = {
  sm: "rounded-[var(--radius-sm)]",
  md: "rounded-[var(--radius-md)]",
  lg: "rounded-[var(--radius-lg)]",
  pill: "rounded-[var(--radius-pill)]",
  full: "rounded-full",
};

// Purely decorative; wrap a group of skeletons in <LoadingState> so screen
// readers get one announcement instead of one per placeholder.
export function Skeleton({ className = "", rounded = "md" }: SkeletonProps) {
  return <div aria-hidden="true" className={["bg-surface-sunken animate-pulse", ROUNDED[rounded], className].join(" ")} />;
}

export function LoadingState({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
