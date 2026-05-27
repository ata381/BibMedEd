interface SkeletonProps {
  className?: string;
  rounded?: "sm" | "md" | "lg" | "pill" | "full";
  "aria-label"?: string;
}

const ROUNDED = {
  sm: "rounded-[var(--radius-sm)]",
  md: "rounded-[var(--radius-md)]",
  lg: "rounded-[var(--radius-lg)]",
  pill: "rounded-[var(--radius-pill)]",
  full: "rounded-full",
};

export function Skeleton({ className = "", rounded = "md", ...rest }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={[
        "bg-surface-sunken animate-pulse",
        ROUNDED[rounded],
        className,
      ].join(" ")}
      {...rest}
    />
  );
}
