import type { ReactNode } from "react";

export interface RankedDatum {
  label: string;
  value: number;
  note?: ReactNode;
}

interface RankedBarsProps {
  data: RankedDatum[];
  valueLabel: string;
  max?: number;
  className?: string;
}

// A ranked list with an inline proportional bar per row — reads as a table
// (rank, name, value) while still showing relative magnitude at a glance.
export function RankedBars({ data, valueLabel, max, className = "" }: RankedBarsProps) {
  const top = max ?? Math.max(...data.map((d) => d.value), 1);
  return (
    <ol className={`divide-y divide-divider ${className}`}>
      {data.map((d, i) => {
        const pct = Math.max(2, Math.round((d.value / top) * 100));
        return (
          <li key={`${d.label}-${i}`} className="grid grid-cols-[1.5rem_1fr_auto] items-center gap-x-3 py-2.5">
            <span className="numeral text-xs text-on-surface-subtle">{String(i + 1).padStart(2, "0")}</span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="text-sm font-semibold text-on-surface truncate max-w-full">{d.label}</span>
                {d.note ? <span className="text-xs text-on-surface-subtle whitespace-nowrap">{d.note}</span> : null}
              </div>
              <div aria-hidden="true" className="mt-1.5 h-1.5 w-full rounded-[var(--radius-xs)] bg-surface-sunken overflow-hidden">
                <div className="h-full rounded-[var(--radius-xs)] bg-chart-3" style={{ width: `${pct}%` }} />
              </div>
            </div>
            <span className="numeral text-lg text-on-surface tabular-nums">
              {d.value.toLocaleString()}
              <span className="sr-only"> {valueLabel}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
