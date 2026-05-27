"use client";

import { useRef, type ReactNode } from "react";

export interface TabItem<T extends string = string> {
  value: T;
  label: string;
  icon?: string;
  badge?: ReactNode;
}

interface TabsProps<T extends string = string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
  className?: string;
}

export function Tabs<T extends string = string>({
  items,
  value,
  onChange,
  ariaLabel = "Tabs",
  className = "",
}: TabsProps<T>) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const focusByIndex = (i: number) => {
    const idx = (i + items.length) % items.length;
    refs.current[items[idx].value]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={`inline-flex items-center gap-1 p-1 rounded-[var(--radius-md)] bg-surface-sunken ${className}`}
    >
      {items.map((item, i) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            ref={(el) => {
              refs.current[item.value] = el;
            }}
            role="tab"
            aria-selected={active}
            aria-controls={`panel-${item.value}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(item.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") {
                e.preventDefault();
                focusByIndex(i + 1);
              } else if (e.key === "ArrowLeft") {
                e.preventDefault();
                focusByIndex(i - 1);
              } else if (e.key === "Home") {
                e.preventDefault();
                focusByIndex(0);
              } else if (e.key === "End") {
                e.preventDefault();
                focusByIndex(items.length - 1);
              }
            }}
            className={[
              "inline-flex items-center gap-2 px-4 h-9 rounded-[var(--radius-sm)]",
              "text-sm font-semibold cursor-pointer",
              "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
              "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
              active
                ? "bg-surface-raised text-primary elev-1"
                : "text-on-surface-muted hover:text-on-surface hover:bg-surface-raised/60",
            ].join(" ")}
            style={{ fontFamily: "var(--font-display)" }}
          >
            {item.icon ? (
              <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: "1.05em" }}>
                {item.icon}
              </span>
            ) : null}
            {item.label}
            {item.badge ? <span className="ml-1">{item.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
