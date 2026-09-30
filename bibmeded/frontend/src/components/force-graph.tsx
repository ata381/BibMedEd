"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { Icon } from "@/components/ui";
import { useElementSize } from "@/hooks/use-element-size";

interface GraphNode {
  id: string;
  label?: string;
  size?: number;
}

interface GraphLink {
  source: string;
  target: string;
  weight?: number;
}

interface ForceGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
  width?: number;
  height?: number;
}

type SimNode = GraphNode & d3.SimulationNodeDatum;
type SimLink = d3.SimulationLinkDatum<SimNode> & { weight?: number };

const LARGE_GRAPH = 200;
const KEEP_DENSEST = 100;
const LABELLED_NODES = 8;
const SETTLE_TICKS = 300;
const DRAG_SETTLE_TICKS = 30;
const DRAG_ALPHA = 0.3;
const ZOOM_EXTENT: [number, number] = [0.3, 4];
const FILL_STEPS = ["var(--color-chart-3)", "var(--color-chart-4)", "var(--color-chart-5)"];

const CONTROL_CLASSES =
  "inline-flex items-center justify-center w-9 h-9 rounded-[var(--radius-sm)] bg-surface-raised border border-divider text-on-surface-muted hover:text-on-surface hover:border-outline-strong cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2";

function nodeRadius(size: number | undefined, maxSize: number) {
  return 4 + ((size ?? 1) / maxSize) * 10;
}

const LABEL_MAX_CHARS = 18;

function shortLabel(node: GraphNode) {
  const name = (String(node.label || node.id).split(",")[0] ?? "").trim();
  if (name.length <= LABEL_MAX_CHARS) return name;
  const cut = name.slice(0, LABEL_MAX_CHARS + 1);
  const lastSpace = cut.lastIndexOf(" ");
  const head = lastSpace > 0 ? cut.slice(0, lastSpace) : name.slice(0, LABEL_MAX_CHARS);
  return `${head.trimEnd()}…`;
}

export function ForceGraph({ nodes, links, width: fixedWidth, height: fixedHeight }: ForceGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [containerRef, measured] = useElementSize<HTMLDivElement>();
  const width = fixedWidth ?? Math.max(measured.width, 320);
  const height = fixedHeight ?? Math.max(measured.height, 320);
  const maxNodeSize = nodes.reduce((m, n) => Math.max(m, n.size ?? 1), 1);

  // Large graphs cap to the densest 100 nodes so the layout stays readable.
  const autoMinPubs = useMemo(() => {
    if (nodes.length <= LARGE_GRAPH) return 0;
    const sizes = nodes.map((n) => n.size ?? 0).sort((a, b) => b - a);
    return sizes[Math.min(KEEP_DENSEST - 1, sizes.length - 1)] ?? 0;
  }, [nodes]);

  const [userMinPubs, setUserMinPubs] = useState<number | null>(null);
  const minPubs = userMinPubs ?? autoMinPubs;

  const filtered = useMemo(() => {
    const filteredNodes = nodes.filter((n) => (n.size ?? 0) >= minPubs);
    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredLinks = links.filter((l) => nodeIds.has(l.source) && nodeIds.has(l.target));
    return { nodes: filteredNodes, links: filteredLinks };
  }, [nodes, links, minPubs]);

  useEffect(() => {
    if (!svgRef.current || filtered.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    const g = svg.append("g");

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent(ZOOM_EXTENT)
      .on("zoom", (event) => g.attr("transform", event.transform));
    svg.call(zoom);
    svg.call(zoom.transform, d3.zoomTransform(svg.node()!));
    zoomRef.current = zoom;

    const simNodes: SimNode[] = filtered.nodes.map((n) => ({ ...n }));
    const simLinks: SimLink[] = filtered.links.map((l) => ({ ...l }));
    const maxWeight = simLinks.reduce((m, l) => Math.max(m, l.weight ?? 1), 1);
    const maxSize = simNodes.reduce((m, n) => Math.max(m, n.size ?? 1), 1);
    const fill = d3.scaleQuantize<string>().domain([0, maxSize]).range(FILL_STEPS);
    const neighbours = new Map<string, Set<string>>();
    for (const l of filtered.links) {
      (neighbours.get(l.source) ?? neighbours.set(l.source, new Set()).get(l.source))!.add(l.target);
      (neighbours.get(l.target) ?? neighbours.set(l.target, new Set()).get(l.target))!.add(l.source);
    }

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const simulation = d3
      .forceSimulation(simNodes)
      .force("link", d3.forceLink<SimNode, SimLink>(simLinks).id((d) => d.id).distance(70))
      .force("charge", d3.forceManyBody().strength(-140))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide<SimNode>().radius((d) => nodeRadius(d.size, maxSize) + 3));

    const link = g
      .append("g")
      .selectAll("line")
      .data(simLinks)
      .join("line")
      .attr("stroke", "var(--color-outline-strong)")
      .attr("stroke-opacity", 0.55)
      .attr("stroke-width", (d) => 0.75 + ((d.weight ?? 1) / maxWeight) * 3);

    const node = g
      .append("g")
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(simNodes)
      .join("circle")
      .attr("r", (d) => nodeRadius(d.size, maxSize))
      .attr("fill", (d) => fill(d.size ?? 1))
      .attr("stroke", "var(--color-surface-raised)")
      .attr("stroke-width", 1.5)
      .style("cursor", "grab")
      .call(
        d3
          .drag<SVGCircleElement, SimNode>()
          .on("start", (event, d) => {
            if (!reducedMotion && !event.active) simulation.alphaTarget(DRAG_ALPHA).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
            if (reducedMotion) {
              simulation.alpha(DRAG_ALPHA).tick(DRAG_SETTLE_TICKS);
              render();
            }
          })
          .on("end", (event, d) => {
            if (!reducedMotion && !event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    node.append("title").text((d) => d.label || d.id);

    const topIds = new Set(
      [...simNodes].sort((a, b) => (b.size ?? 0) - (a.size ?? 0)).slice(0, LABELLED_NODES).map((n) => n.id)
    );
    node.filter((d) => topIds.has(d.id)).attr("tabindex", 0);
    const labels = g
      .append("g")
      .selectAll("text")
      .data(simNodes.filter((n) => topIds.has(n.id)))
      .join("text")
      .text(shortLabel)
      .attr("font-size", "11px")
      .attr("font-weight", "600")
      .attr("fill", "var(--color-on-surface)")
      .attr("stroke", "var(--color-surface-sunken)")
      .attr("stroke-width", 3)
      .attr("paint-order", "stroke")
      .attr("text-anchor", "middle")
      .attr("pointer-events", "none")
      .attr("dy", (d) => -(nodeRadius(d.size, maxSize) + 5));

    const highlight = (focus: SimNode | null) => {
      const keep = focus ? new Set([focus.id, ...(neighbours.get(focus.id) ?? [])]) : null;
      node.attr("opacity", (d) => (!keep || keep.has(d.id) ? 1 : 0.2));
      labels.attr("opacity", (d) => (!keep || keep.has(d.id) ? 1 : 0.2));
      link.attr("stroke-opacity", (d) => {
        if (!focus) return 0.55;
        const s = (d.source as SimNode).id;
        const t = (d.target as SimNode).id;
        return s === focus.id || t === focus.id ? 0.9 : 0.08;
      });
    };
    node
      .on("mouseenter focus", (_, d) => highlight(d))
      .on("mouseleave blur", () => highlight(null));

    const render = () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);
      node.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
      labels.attr("x", (d) => d.x ?? 0).attr("y", (d) => d.y ?? 0);
    };

    if (reducedMotion) {
      simulation.stop();
      simulation.tick(SETTLE_TICKS);
      render();
      simulation.on("tick", render);
    } else {
      simulation.on("tick", render);
    }

    return () => {
      simulation.stop();
    };
  }, [filtered, width, height]);

  const zoomBy = (factor: number) => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current).transition().duration(200).call(zoomRef.current.scaleBy, factor);
  };
  const resetZoom = () => {
    if (!svgRef.current || !zoomRef.current) return;
    d3.select(svgRef.current).transition().duration(200).call(zoomRef.current.transform, d3.zoomIdentity);
  };

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full min-h-[240px] gap-2 text-on-surface-muted text-sm">
        <Icon name="network" size={18} />
        No network data available
      </div>
    );
  }

  const summaryNodes = [...filtered.nodes].sort((a, b) => (b.size ?? 0) - (a.size ?? 0)).slice(0, 10);
  const sliderId = "force-graph-min-pubs";

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[320px]">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="absolute inset-0 w-full h-full"
        role="img"
        aria-label={`Network graph: ${filtered.nodes.length} nodes, ${filtered.links.length} links. Pan and zoom to explore.`}
      />
      {/* Accessible alternative to the interactive SVG (WCAG 1.1.1). */}
      <div className="sr-only">
        <p>Top {summaryNodes.length} nodes by size:</p>
        <ul>
          {summaryNodes.map((n) => (
            <li key={n.id}>
              {n.label ?? n.id} — {n.size ?? 0}
            </li>
          ))}
        </ul>
      </div>

      <div role="group" aria-label="Graph zoom" className="absolute top-3 left-3 flex flex-col gap-1">
        <button type="button" onClick={() => zoomBy(1.4)} aria-label="Zoom in" className={CONTROL_CLASSES}>
          <Icon name="zoomIn" size={16} />
        </button>
        <button type="button" onClick={() => zoomBy(1 / 1.4)} aria-label="Zoom out" className={CONTROL_CLASSES}>
          <Icon name="zoomOut" size={16} />
        </button>
        <button type="button" onClick={resetZoom} aria-label="Reset zoom" className={CONTROL_CLASSES}>
          <Icon name="fit" size={16} />
        </button>
      </div>

      {maxNodeSize > 1 && (
        <div className="absolute top-3 right-3 bg-surface-raised/95 backdrop-blur-sm rounded-[var(--radius-md)] px-3 py-2 border border-divider elev-1">
          <label htmlFor={sliderId} className="eyebrow block mb-1.5">
            Min. publications: {minPubs}
          </label>
          <input
            id={sliderId}
            type="range"
            min={0}
            max={Math.ceil(maxNodeSize * 0.5)}
            value={minPubs}
            onChange={(e) => setUserMinPubs(Number(e.target.value))}
            className="w-28 h-6 block"
            aria-label={`Filter nodes by minimum publication count, currently ${minPubs}`}
          />
          <p className="text-xs text-on-surface-subtle mt-1 tabular-nums">
            {filtered.nodes.length} / {nodes.length} nodes
          </p>
        </div>
      )}

      <p className="absolute bottom-3 left-3 right-3 text-xs text-on-surface-subtle pointer-events-none">
        <span className="font-semibold text-on-surface-muted">Node size</span> = publications ·{" "}
        <span className="font-semibold text-on-surface-muted">edge width</span> = co-authored papers · drag nodes, scroll to zoom
      </p>
    </div>
  );
}
