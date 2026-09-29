"use client";

import { useRef, type ReactNode } from "react";
import { Icon, type IconName } from "./icon";

export interface TabItem<T extends string = string> {
  value: T;
  label: string;
  icon?: IconName;
  badge?: ReactNode;
}

interface TabsProps<T extends string = string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
  className?: string;
}

const KEY_TO_OFFSET: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1 };

export function Tabs<T extends string = string>({ items, value, onChange, ariaLabel = "Tabs", className = "" }: TabsProps<T>) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const focusByIndex = (i: number) => {
    const idx = (i + items.length) % items.length;
    refs.current[items[idx].value]?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent, i: number) => {
    if (e.key in KEY_TO_OFFSET) {
      e.preventDefault();
      focusByIndex(i + KEY_TO_OFFSET[e.key]);
    } else if (e.key === "Home") {
      e.preventDefault();
      focusByIndex(0);
    } else if (e.key === "End") {
      e.preventDefault();
      focusByIndex(items.length - 1);
    }
  };

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={`flex w-full items-end gap-1 sm:gap-5 overflow-x-auto border-b border-divider ${className}`}
    >
      {items.map((item, i) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            id={`tab-${item.value}`}
            ref={(el) => {
              refs.current[item.value] = el;
            }}
            role="tab"
            aria-selected={active}
            aria-controls={`panel-${item.value}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(item.value)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            className={[
              "flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-2 sm:px-1 h-11 -mb-px",
              "text-sm font-semibold whitespace-nowrap cursor-pointer border-b-2",
              "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
              "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:-outline-offset-2 focus-visible:rounded-[var(--radius-sm)]",
              active
                ? "border-on-surface text-on-surface"
                : "border-transparent text-on-surface-muted hover:text-on-surface hover:border-outline",
            ].join(" ")}
          >
            {item.icon ? <Icon name={item.icon} size={16} /> : null}
            {item.label}
            {item.badge ? <span className="ml-1">{item.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
