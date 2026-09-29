"use client";

import Link, { type LinkProps } from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Icon, type IconName } from "./icon";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md" | "lg";

interface StyleProps {
  variant?: Variant;
  size?: Size;
  fullWidth?: boolean;
  className?: string;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-ink text-on-ink hover:bg-ink-hover disabled:opacity-40",
  secondary:
    "bg-primary-container text-on-primary-container hover:bg-secondary-container disabled:opacity-40",
  ghost: "bg-transparent text-on-surface hover:bg-surface-hover disabled:opacity-40",
  outline:
    "bg-transparent text-on-surface border border-outline-strong hover:bg-surface-hover hover:border-on-surface disabled:opacity-40",
  danger: "bg-danger text-on-danger hover:opacity-90 disabled:opacity-40",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-9 px-3 text-xs gap-1.5",
  md: "h-11 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2.5",
};

const ICON_SIZE: Record<Size, number> = { sm: 15, md: 17, lg: 19 };

export function buttonClasses({ variant = "primary", size = "md", fullWidth = false, className = "" }: StyleProps) {
  return [
    "inline-flex items-center justify-center font-semibold rounded-[var(--radius-md)] whitespace-nowrap",
    "transition-[background-color,border-color,color,opacity] duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
    "cursor-pointer disabled:cursor-not-allowed",
    "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
    SIZE_CLASSES[size],
    VARIANT_CLASSES[variant],
    fullWidth ? "w-full" : "",
    className,
  ].join(" ");
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, StyleProps {
  loading?: boolean;
  leadingIcon?: IconName;
  trailingIcon?: IconName;
  children?: ReactNode;
}

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
  const iconSize = ICON_SIZE[size];
  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={buttonClasses({ variant, size, fullWidth, className })}
      {...rest}
    >
      {loading ? (
        <Icon name="loader" size={iconSize} className="animate-spin" />
      ) : leadingIcon ? (
        <Icon name={leadingIcon} size={iconSize} />
      ) : null}
      {children}
      {trailingIcon && !loading ? <Icon name={trailingIcon} size={iconSize} /> : null}
    </button>
  );
});

interface ButtonLinkProps extends StyleProps, Omit<LinkProps, "className"> {
  leadingIcon?: IconName;
  trailingIcon?: IconName;
  children?: ReactNode;
  "aria-label"?: string;
}

// A link that looks like a button — avoids nesting <button> inside <a>,
// which is invalid HTML and confuses assistive tech.
export function ButtonLink({
  variant = "primary",
  size = "md",
  fullWidth = false,
  className = "",
  leadingIcon,
  trailingIcon,
  children,
  ...rest
}: ButtonLinkProps) {
  const iconSize = ICON_SIZE[size];
  return (
    <Link className={buttonClasses({ variant, size, fullWidth, className })} {...rest}>
      {leadingIcon ? <Icon name={leadingIcon} size={iconSize} /> : null}
      {children}
      {trailingIcon ? <Icon name={trailingIcon} size={iconSize} /> : null}
    </Link>
  );
}
