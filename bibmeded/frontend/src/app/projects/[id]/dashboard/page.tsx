"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { analysisApi, projectsApi, Project } from "@/lib/api";
import toast from "react-hot-toast";
import { ForceGraph } from "@/components/force-graph";
import { Tabs, type TabItem } from "@/components/ui";

type AnalysisData = Record<string, unknown>;
type DashboardTab = "overview" | "authors" | "networks" | "citations";

const TABS: TabItem<DashboardTab>[] = [
  { value: "overview", label: "Overview" },
  { value: "authors", label: "Authors" },
  { value: "networks", label: "Networks" },
  { value: "citations", label: "Citations" },
];

export default function Dashboard() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [project, setProject] = useState<Project | null>(null);
  const [analyses, setAnalyses] = useState<Record<string, AnalysisData>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Use an abort controller so a slow analysis chain for a previously-viewed
    // project can't resolve after navigation and clobber the currently-viewed
    // project's state (same pattern as results/page.tsx).
    const ctrl = new AbortController();
    const load = async () => {
      try {
        const proj = await projectsApi.get(projectId);
        if (ctrl.signal.aborted) return;
        setProject(proj.data);
        const types = ["publications", "authors", "countries", "keywords", "citations", "journals"];
        const results: Record<string, AnalysisData> = {};
        for (const t of types) {
          if (ctrl.signal.aborted) return;
          try { const r = await analysisApi.get(projectId, t); results[t] = r.data.results as AnalysisData; }
          catch { try { const r = await analysisApi.run(projectId, t); results[t] = r.data.results as AnalysisData; } catch {} }
        }
        if (ctrl.signal.aborted) return;
        setAnalyses(results);
      } catch {
        if (!ctrl.signal.aborted) toast.error("Failed to load analysis data.");
      }
      if (!ctrl.signal.aborted) setLoading(false);
    };
    load();
    return () => ctrl.abort();
  }, [projectId]);

  if (loading) return (
    <div className="flex items-center justify-center h-[60vh] text-on-surface-muted">
      <span className="material-symbols-outlined animate-spin mr-3">sync</span>Running all analyses...
    </div>
  );

  const pub = analyses.publications || {};
  const auth = analyses.authors || {};
  const cite = analyses.citations || {};
  const kw = analyses.keywords || {};

  const yearlyCounts = (pub.yearly_counts as Array<{year:number;count:number}>) || [];
  const topAuthors = (auth.top_authors as Array<{name:string;pub_count:number;citation_sum:number}>) || [];
  const mostCited = (cite.most_cited as Array<{title:string;pmid:string;year:number;citation_count:number}>) || [];
  const topKeywords = (kw.top_keywords as Array<{term:string;count:number}>) || [];
  const coauthorNetwork = (auth.coauthorship_network as {nodes: Array<{id:string;label?:string;size?:number}>; links: Array<{source:string;target:string;weight?:number}>}) || {nodes:[], links:[]};
  const totalPubs = (pub.total as number) || 0;
  const totalAuthors = (auth.total_authors as number) || 0;
  const totalCitations = (cite.total_citations as number) || 0;
  const maxYearCount = Math.max(...yearlyCounts.map(y => y.count), 1);

  if (totalPubs === 0 && !loading) return (
    <div className="max-w-7xl mx-auto px-2 py-6">
      <div className="text-center py-20">
        <span className="material-symbols-outlined text-6xl text-on-surface-subtle mb-4 block">query_stats</span>
        <h3 className="text-xl font-bold text-on-surface mb-2" style={{fontFamily:"var(--font-display)"}}>No Publications to Analyze</h3>
        <p className="text-sm text-on-surface-muted mb-6">Run a search first to populate results, then come back here for analysis.</p>
        <button onClick={() => router.push(`/projects/${projectId}/search`)}
          className="px-6 py-2.5 bg-primary text-white rounded-lg font-bold text-sm hover:opacity-90 transition">
          Go to Search
        </button>
      </div>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto px-2 py-6">
      {/* Header */}
      <section className="mb-8">
        <h1 className="text-3xl font-extrabold text-on-surface tracking-tight" style={{fontFamily:"var(--font-display)"}}>Analysis Overview</h1>
        <p className="text-on-surface-muted font-medium">{project?.name}</p>
      </section>

      {/* Tabs */}
      <div className="mb-8">
        <Tabs items={TABS} value={activeTab} onChange={setActiveTab} ariaLabel="Dashboard sections" />
      </div>

      {/* Metric Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-10">
        <MetricCard icon="description" label="Total Publications" value={totalPubs.toLocaleString()} badge="Pubs" badgeColor="text-primary bg-blue-50" />
        <MetricCard icon="group" label="Unique Authors" value={totalAuthors.toLocaleString()} badge="Global" badgeColor="text-primary bg-blue-50" />
        <MetricCard icon="format_quote" label="Total Citations" value={totalCitations.toLocaleString()} badge="Citations" badgeColor="text-primary bg-blue-50" />
        <MetricCard icon="star" label="Keywords Tracked" value={topKeywords.length.toString()} badge="Active" badgeColor="text-on-secondary-container bg-secondary-container" />
      </div>

      {/* Visual Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-6 gap-8">
        {/* Publication Trends */}
        <div className="lg:col-span-4 bg-surface-raised rounded-xl p-8 shadow-sm">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h3 className="font-bold text-xl text-primary" style={{fontFamily:"var(--font-display)"}}>Publication Trends</h3>
              <p className="text-sm text-on-surface-muted">Annual publication count</p>
            </div>
          </div>
          <div className="h-64 flex items-end justify-between gap-4 px-2">
            {yearlyCounts.map((y, i) => (
              <div key={y.year} className={`flex-1 rounded-t-lg relative group transition-all hover:opacity-80 ${i === yearlyCounts.length - 1 ? "bg-primary" : "bg-surface-sunken hover:bg-primary-hover"}`}
                style={{ height: `${(y.count / maxYearCount) * 100}%`, minHeight: 8 }}>
                <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-code-bg text-code-fg text-[10px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                  {y.count} Pubs
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-4 text-[10px] font-bold text-slate-400 uppercase tracking-widest px-2">
            {yearlyCounts.map(y => <span key={y.year}>{y.year}</span>)}
          </div>
        </div>

        {/* Top Authors */}
        <div className="lg:col-span-2 bg-surface-raised rounded-xl p-8 shadow-sm">
          <h3 className="font-bold text-xl text-primary mb-6" style={{fontFamily:"var(--font-display)"}}>Top Authors</h3>
          <div className="space-y-5">
            {topAuthors.slice(0, 5).map((a, i) => (
              <div key={i} className="flex items-center gap-4 group">
                <div className="text-sm font-bold text-slate-300">{String(i+1).padStart(2,"0")}</div>
                <div className="w-10 h-10 rounded-full bg-primary-hover flex items-center justify-center text-white font-bold text-xs">
                  {a.name.split(",")[0]?.slice(0,2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-on-surface truncate group-hover:text-primary transition-colors">{a.name}</p>
                  <p className="text-[10px] text-slate-400">{a.citation_sum} citations</p>
                </div>
                <div className="text-xs font-bold text-on-secondary-container bg-secondary-container px-2 py-1 rounded">{a.pub_count}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Network Preview */}
        <div className="lg:col-span-3 bg-surface-raised rounded-xl p-8 shadow-sm flex flex-col min-h-[400px]">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h3 className="font-bold text-xl text-primary" style={{fontFamily:"var(--font-display)"}}>Network Preview</h3>
              <p className="text-sm text-on-surface-muted">Co-authorship clustering</p>
            </div>
            <span className="material-symbols-outlined text-on-surface-muted">hub</span>
          </div>
          <div className="flex-1 relative overflow-hidden rounded-xl bg-slate-50 border border-slate-100/50">
            <ForceGraph
              nodes={coauthorNetwork.nodes || []}
              links={coauthorNetwork.links || []}
            />
            <div className="absolute bottom-4 left-4 right-4 bg-surface-raised/60 backdrop-blur-md p-3 rounded-lg border border-white/40">
              <p className="text-[10px] font-bold text-on-surface uppercase tracking-wide">{coauthorNetwork.nodes?.length || 0} Authors in Network</p>
              <p className="text-[10px] text-slate-500">Drag nodes to explore · scroll to zoom</p>
            </div>
          </div>
        </div>

        {/* Top Keywords */}
        <div className="lg:col-span-3 bg-surface-raised rounded-xl p-8 shadow-sm">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h3 className="font-bold text-xl text-primary" style={{fontFamily:"var(--font-display)"}}>Top Keywords</h3>
              <p className="text-sm text-on-surface-muted">Most frequent terms</p>
            </div>
            <span className="material-symbols-outlined text-on-surface-muted">label</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {topKeywords.slice(0, 20).map((k, i) => {
              const maxCount = topKeywords[0]?.count || 1;
              const opacity = 0.5 + (k.count / maxCount) * 0.5;
              return (
                <span key={i} className="px-3 py-1.5 bg-primary-container text-primary rounded-full text-xs font-bold" style={{ opacity }}>
                  {k.term} ({k.count})
                </span>
              );
            })}
          </div>
        </div>

        {/* Most Cited */}
        <div className="lg:col-span-6 bg-surface-raised rounded-xl p-8 shadow-sm">
          <h3 className="font-bold text-xl text-primary mb-6" style={{fontFamily:"var(--font-display)"}}>Most Cited Publications</h3>
          <div className="space-y-4">
            {mostCited.slice(0, 5).map((c, i) => (
              <div key={i} className="flex items-start gap-4 group cursor-pointer">
                <span className="text-xs font-bold text-slate-300 mt-1">{String(i+1).padStart(2,"0")}</span>
                <div className="flex-1">
                  <h4 className="text-sm font-bold text-on-surface leading-snug group-hover:text-primary transition-colors">{c.title}</h4>
                  <p className="text-[11px] text-on-surface-muted mt-1">{c.year} · PMID: {c.pmid}</p>
                </div>
                <div className="text-sm font-extrabold text-primary">{c.citation_count}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value, badge, badgeColor }: { icon: string; label: string; value: string; badge: string; badgeColor: string }) {
  return (
    <div className="p-6 bg-surface-raised rounded-xl shadow-sm hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-4">
        <span className="text-slate-400 material-symbols-outlined">{icon}</span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badgeColor}`}>{badge}</span>
      </div>
      <p className="text-3xl font-extrabold text-primary" style={{fontFamily:"var(--font-display)"}}>{value}</p>
      <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mt-1">{label}</p>
    </div>
  );
}
