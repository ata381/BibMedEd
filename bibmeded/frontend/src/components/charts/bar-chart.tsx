"use client";

import { useElementSize } from "@/hooks/use-element-size";

export interface BarDatum {
  label: string;
  value: number;
}

interface BarChartProps {
  data: BarDatum[];
  ariaLabel: string;
  unit?: string;
  height?: number;
  className?: string;
}

const MARGIN = { top: 28, right: 8, bottom: 30, left: 36 };
const MAX_X_LABELS = 12;

function niceMax(max: number) {
  if (max <= 4) return 4;
  const magnitude = 10 ** Math.floor(Math.log10(max));
  const step = magnitude / 2;
  return Math.ceil(max / step) * step;
}

// Annual counts drawn as a proper SVG chart: y gridlines, value labels, and
// an accessible data table for screen readers. Sizes itself to the container.
export function BarChart({ data, ariaLabel, unit = "publications", height = 260, className = "" }: BarChartProps) {
  const [ref, { width: measured }] = useElementSize<HTMLDivElement>();
  const width = Math.max(measured, 280);
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = height - MARGIN.top - MARGIN.bottom;
  const yMax = niceMax(Math.max(...data.map((d) => d.value), 1));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * yMax);
  const slot = data.length > 0 ? innerW / data.length : innerW;
  const barW = Math.max(6, Math.min(56, slot * 0.62));
  const labelEvery = Math.max(1, Math.ceil(data.length / MAX_X_LABELS));
  const yFor = (v: number) => MARGIN.top + innerH - (v / yMax) * innerH;
  const lastIndex = data.length - 1;

  return (
    <div ref={ref} className={`w-full ${className}`}>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={ariaLabel}
        className="block font-sans"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={MARGIN.left}
              x2={width - MARGIN.right}
              y1={yFor(t)}
              y2={yFor(t)}
              stroke="var(--color-chart-grid)"
              strokeDasharray={t === 0 ? undefined : "2 4"}
            />
            <text
              x={MARGIN.left - 8}
              y={yFor(t)}
              dy="0.35em"
              textAnchor="end"
              fontSize="11"
              fill="var(--color-on-surface-subtle)"
              className="tabular-nums"
            >
              {Number.isInteger(t) ? t : t.toFixed(1)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = MARGIN.left + slot * i + (slot - barW) / 2;
          const y = yFor(d.value);
          const isLast = i === lastIndex;
          return (
            <g key={d.label}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={Math.max(0, MARGIN.top + innerH - y)}
                fill={isLast ? "var(--color-chart-5)" : "var(--color-chart-3)"}
                rx="2"
              />
              {slot >= 26 ? (
                <text
                  x={x + barW / 2}
                  y={y - 6}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="600"
                  fill="var(--color-on-surface-muted)"
                  className="tabular-nums"
                >
                  {d.value}
                </text>
              ) : null}
              {i % labelEvery === 0 || isLast ? (
                <text
                  x={x + barW / 2}
                  y={height - 10}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="600"
                  fill="var(--color-on-surface-subtle)"
                  className="tabular-nums"
                >
                  {d.label}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
      <ul className="sr-only">
        {data.map((d) => (
          <li key={d.label}>
            {d.label}: {d.value} {unit}
          </li>
        ))}
      </ul>
    </div>
  );
}
