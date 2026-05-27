"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leadingIcon?: string;
  trailingIcon?: string;
  fullWidth?: boolean;
  children?: ReactNode;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-primary text-on-primary hover:bg-primary-hover active:bg-primary-hover disabled:opacity-40",
  secondary:
    "bg-secondary-container text-on-secondary-container hover:bg-secondary hover:text-on-secondary disabled:opacity-40",
  ghost:
    "bg-transparent text-on-surface hover:bg-surface-hover disabled:opacity-40",
  outline:
    "bg-transparent text-on-surface border border-outline-strong hover:bg-surface-hover disabled:opacity-40",
  danger:
    "bg-danger text-on-danger hover:bg-danger/90 disabled:opacity-40",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-9 px-3 text-xs gap-1.5",
  md: "h-11 px-5 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    leadingIcon,
    trailingIcon,
    fullWidth = false,
    disabled,
    className = "",
    children,
    type = "button",
    ...rest
  },
  ref
) {
  const isDisabled = disabled || loading;
  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={[
        "inline-flex items-center justify-center font-semibold rounded-md",
        "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
        "cursor-pointer disabled:cursor-not-allowed",
        "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
        SIZE_CLASSES[size],
        VARIANT_CLASSES[variant],
        fullWidth ? "w-full" : "",
        className,
      ].join(" ")}
      style={{ fontFamily: "var(--font-display)" }}
      {...rest}
    >
      {loading ? (
        <span className="material-symbols-outlined animate-spin" aria-hidden="true" style={{ fontSize: "1.1em" }}>
          progress_activity
        </span>
      ) : leadingIcon ? (
        <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: "1.1em" }}>
          {leadingIcon}
        </span>
      ) : null}
      {children}
      {trailingIcon && !loading ? (
        <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: "1.1em" }}>
          {trailingIcon}
        </span>
      ) : null}
    </button>
  );
});
