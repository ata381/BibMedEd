// Decorative co-authorship figure for the empty workspace. Hand-placed so it
// renders identically everywhere (no simulation, no runtime dependency) and
// draws its edges on first paint; the animation is stroke-only and is
// disabled under prefers-reduced-motion.
const NODES: Array<[number, number, number, number]> = [
  // x, y, radius, fill step (0–2)
  [238, 176, 16, 2],
  [150, 110, 11, 1],
  [330, 96, 12, 1],
  [352, 226, 10, 1],
  [140, 250, 9, 1],
  [86, 168, 7, 0],
  [204, 62, 7, 0],
  [292, 292, 8, 0],
  [410, 150, 7, 0],
  [420, 290, 6, 0],
  [60, 84, 5, 0],
  [96, 318, 6, 0],
  [232, 322, 5, 0],
  [388, 44, 5, 0],
];

const EDGES: Array<[number, number, number]> = [
  // from, to, weight
  [0, 1, 3], [0, 2, 3], [0, 3, 2], [0, 4, 2], [0, 6, 1], [0, 7, 1],
  [1, 5, 2], [1, 6, 1], [1, 10, 1], [5, 10, 1],
  [2, 8, 2], [2, 13, 1], [8, 13, 1], [3, 8, 1], [3, 9, 1], [9, 7, 1],
  [4, 11, 1], [4, 12, 1], [7, 12, 1], [1, 4, 1],
];

const FILL = ["var(--color-chart-3)", "var(--color-chart-4)", "var(--color-chart-5)"];

export function NetworkFigure({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 480 360"
      className={`w-full h-auto ${className}`}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <pattern id="fig-grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0v24" fill="none" stroke="var(--color-chart-grid)" strokeWidth="0.75" />
        </pattern>
      </defs>
      <rect width="480" height="360" fill="url(#fig-grid)" opacity="0.7" />
      <g stroke="var(--color-outline-strong)" strokeLinecap="round" strokeOpacity="0.6">
        {EDGES.map(([a, b, w], i) => (
          <line
            key={i}
            x1={NODES[a][0]}
            y1={NODES[a][1]}
            x2={NODES[b][0]}
            y2={NODES[b][1]}
            strokeWidth={0.8 + w}
            pathLength={1}
            className="draw"
            style={{ animationDelay: `${180 + i * 45}ms` }}
          />
        ))}
      </g>
      <g stroke="var(--color-surface-raised)" strokeWidth="2">
        {NODES.map(([x, y, r, step], i) => (
          <circle key={i} cx={x} cy={y} r={r} fill={FILL[step]} className="rise" style={{ "--rise-index": i } as React.CSSProperties} />
        ))}
      </g>
      <g fontFamily="var(--font-sans)" fontSize="11" fontWeight="600" fill="var(--color-on-surface)" stroke="var(--color-surface)" strokeWidth="3" paintOrder="stroke">
        <text x={238} y={152} textAnchor="middle">Garcia E</text>
        <text x={150} y={92} textAnchor="middle">Chen M</text>
        <text x={330} y={78} textAnchor="middle">Patel A</text>
        <text x={352} y={252} textAnchor="middle">Okafor N</text>
      </g>
    </svg>
  );
}
