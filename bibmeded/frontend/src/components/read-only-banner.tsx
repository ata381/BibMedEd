"use client";

import { Icon } from "@/components/ui";
import { QUICK_START_URL, useReadOnly } from "@/lib/read-only";

export function ReadOnlyBanner() {
  const readOnly = useReadOnly();
  return (
    <div role="status" aria-live="polite">
      {readOnly === true && (
        <p className="mb-8 flex flex-wrap items-center gap-x-3 gap-y-1 border-l-2 border-warning bg-warning-container px-4 py-3 text-sm text-on-surface rounded-r-[var(--radius-md)]">
          <Icon name="eye" size={16} className="text-warning shrink-0" />
          <span>
            <span className="font-semibold">Read-only demo</span> — install locally to run your own searches.
          </span>
          <a
            href={QUICK_START_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-semibold text-primary underline underline-offset-4 decoration-outline hover:decoration-primary focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2 rounded-[var(--radius-xs)]"
          >
            Quick Start
            <Icon name="external" size={14} label="(opens in a new tab)" />
          </a>
        </p>
      )}
    </div>
  );
}
