"use client";

import { useEffect, useRef, useMemo, useState } from "react";
import * as d3 from "d3";

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

export function ForceGraph({ nodes, links, width = 400, height = 350 }: ForceGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const maxNodeSize = nodes.reduce((m, n) => Math.max(m, n.size ?? 1), 1);

  // Derive the auto-threshold during render — no setState in effect.
  // For large graphs (>200 nodes) we cap to the 100th-densest node so the
  // network stays readable; smaller graphs show everything.
  const autoMinPubs = useMemo(() => {
    if (nodes.length <= 200) return 0;
    const sizes = nodes.map(n => n.size ?? 0).sort((a, b) => b - a);
    return sizes[Math.min(99, sizes.length - 1)] ?? 0;
  }, [nodes]);

  // Null = follow auto-floor; a number = explicit user override of the slider.
  const [userMinPubs, setUserMinPubs] = useState<number | null>(null);
  const minPubs = userMinPubs ?? autoMinPubs;

  const filtered = useMemo(() => {
    const filteredNodes = nodes.filter(n => (n.size ?? 0) >= minPubs);
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredLinks = links.filter(l => nodeIds.has(l.source) && nodeIds.has(l.target));
    return { nodes: filteredNodes, links: filteredLinks };
  }, [nodes, links, minPubs]);

  useEffect(() => {
    if (!svgRef.current || filtered.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const g = svg.append("g");

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 4])
        .on("zoom", (event) => g.attr("transform", event.transform))
    );

    const simNodes = filtered.nodes.map(n => ({ ...n }));
    const simLinks = filtered.links.map(l => ({ ...l }));

    const maxWeight = simLinks.reduce((m, l) => Math.max(m, l.weight ?? 1), 1);
    const maxSize = simNodes.reduce((m, n) => Math.max(m, n.size ?? 1), 1);

    const simulation = d3.forceSimulation(simNodes as d3.SimulationNodeDatum[])
      .force("link", d3.forceLink(simLinks as d3.SimulationLinkDatum<d3.SimulationNodeDatum>[])
        .id((d: any) => d.id)
        .distance(80))
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius((d: any) => 6 + (d.size ?? 1) / maxSize * 12));

    const link = g.append("g")
      .selectAll("line")
      .data(simLinks)
      .join("line")
      .attr("stroke", "#c4c6cf")
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", (d: any) => 0.5 + (d.weight ?? 1) / maxWeight * 2.5);

    const node = g.append("g")
      .selectAll<SVGCircleElement, typeof simNodes[number]>("circle")
      .data(simNodes)
      .join("circle")
      .attr("r", (d: any) => 4 + (d.size ?? 1) / maxSize * 10)
      .attr("fill", "#00327a")
      .attr("stroke", "#001e4f")
      .attr("stroke-width", 1)
      .call(d3.drag<SVGCircleElement, any>()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    node.append("title").text((d: any) => d.label || d.id);

    const topNodes = [...simNodes].sort((a, b) => (b.size ?? 0) - (a.size ?? 0)).slice(0, 8);
    const topIds = new Set(topNodes.map(n => n.id));

    const labels = g.append("g")
      .selectAll("text")
      .data(simNodes.filter(n => topIds.has(n.id)))
      .join("text")
      .text((d: any) => String(d.label || d.id).split(",")[0]?.slice(0, 15))
      .attr("font-size", "9px")
      .attr("font-weight", "600")
      .attr("fill", "#191c1e")
      .attr("text-anchor", "middle")
      .attr("dy", (d: any) => -(6 + (d.size ?? 1) / maxSize * 10 + 4));

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);
      node
        .attr("cx", (d: any) => d.x)
        .attr("cy", (d: any) => d.y);
      labels
        .attr("x", (d: any) => d.x)
        .attr("y", (d: any) => d.y);
    });

    return () => { simulation.stop(); };
  }, [filtered, width, height]);

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-on-surface-muted text-sm">
        <span className="material-symbols-outlined mr-2">hub</span>
        No network data available
      </div>
    );
  }

  // Top nodes summary — exposed as a visually-hidden table for screen-reader users
  // who can't operate the interactive SVG. Order matches the rendered force layout.
  const summaryNodes = [...filtered.nodes]
    .sort((a, b) => (b.size ?? 0) - (a.size ?? 0))
    .slice(0, 10);
  const sliderId = "force-graph-min-pubs";

  return (
    <div className="relative w-full h-full">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="w-full h-full"
        role="img"
        aria-label={`Network graph: ${filtered.nodes.length} nodes, ${filtered.links.length} links. Pan and zoom to explore.`}
      />
      {/* Visually-hidden top-nodes table — gives non-sighted users an accessible
          alternative to the interactive SVG (WCAG 1.1.1 non-text content). */}
      <div className="sr-only">
        <p>Top {summaryNodes.length} nodes by size:</p>
        <ul>
          {summaryNodes.map((n) => (
            <li key={n.id}>{n.label ?? n.id} — {n.size ?? 0}</li>
          ))}
        </ul>
      </div>
      {maxNodeSize > 1 && (
        <div className="absolute top-3 right-3 bg-white/80 backdrop-blur-sm rounded-lg px-3 py-2 shadow-sm border border-slate-100">
          <label htmlFor={sliderId} className="text-[9px] font-bold text-on-surface-muted uppercase tracking-widest block mb-1">
            Min. publications: {minPubs}
          </label>
          <input
            id={sliderId}
            type="range"
            min={0}
            max={Math.ceil(maxNodeSize * 0.5)}
            value={minPubs}
            onChange={(e) => setUserMinPubs(Number(e.target.value))}
            className="w-24 h-1 accent-primary"
            aria-label={`Filter nodes by minimum publication count, currently ${minPubs}`}
          />
          <p className="text-[8px] text-on-surface-subtle mt-0.5">{filtered.nodes.length} / {nodes.length} nodes</p>
        </div>
      )}
    </div>
  );
}
