"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { analysisApi, projectsApi, Project } from "@/lib/api";

type AnalysisData = Record<string, unknown>;

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "authors", label: "Authors" },
  { key: "networks", label: "Networks" },
  { key: "citations", label: "Citations" },
];

export default function Dashboard() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const [activeTab, setActiveTab] = useState("overview");
  const [project, setProject] = useState<Project | null>(null);
  const [analyses, setAnalyses] = useState<Record<string, AnalysisData>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const proj = await projectsApi.get(projectId);
        setProject(proj.data);
        const types = ["publications", "authors", "countries", "keywords", "citations", "journals"];
        const results: Record<string, AnalysisData> = {};
        for (const t of types) {
          try { const r = await analysisApi.get(projectId, t); results[t] = r.data.results as AnalysisData; }
          catch { try { const r = await analysisApi.run(projectId, t); results[t] = r.data.results as AnalysisData; } catch {} }
        }
        setAnalyses(results);
      } catch {}
      setLoading(false);
    };
    load();
  }, [projectId]);

  if (loading) return (
    <div className="flex items-center justify-center h-[60vh] text-[#43474e]">
      <span className="material-symbols-outlined animate-spin mr-3">sync</span>Running all analyses...
    </div>
  );

  const pub = analyses.publications || {};
  const auth = analyses.authors || {};
  const cite = analyses.citations || {};
  const kw = analyses.keywords || {};

  const yearlyCounts = (pub as any).yearly_counts as Array<{year:number;count:number}> || [];
  const topAuthors = (auth as any).top_authors as Array<{name:string;pub_count:number;citation_sum:number}> || [];
  const mostCited = (cite as any).most_cited as Array<{title:string;pmid:string;year:number;citation_count:number}> || [];
  const topKeywords = (kw as any).top_keywords as Array<{term:string;count:number}> || [];
  const totalPubs = (pub as any).total || 0;
  const totalAuthors = (auth as any).total_authors || 0;
  const totalCitations = (cite as any).total_citations || 0;
  const maxYearCount = Math.max(...yearlyCounts.map(y => y.count), 1);

  return (
    <div className="max-w-7xl mx-auto px-2 py-6">
      {/* Header */}
      <section className="mb-8">
        <h2 className="text-3xl font-extrabold text-[#191c1e] tracking-tight" style={{fontFamily:"'Manrope',sans-serif"}}>Analysis Overview</h2>
        <p className="text-[#43474e] font-medium">{project?.name}</p>
      </section>

      {/* Tabs */}
      <div className="flex gap-8 mb-8 overflow-x-auto">
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`pb-3 px-1 border-b-2 text-sm whitespace-nowrap transition-colors ${activeTab === tab.key ? "border-[#001e4f] text-[#001e4f] font-bold" : "border-transparent text-[#43474e] font-medium hover:text-[#001e4f]"}`}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Metric Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-10">
        <MetricCard icon="description" label="Total Publications" value={totalPubs.toLocaleString()} badge="Pubs" badgeColor="text-[#001e4f] bg-blue-50" />
        <MetricCard icon="group" label="Unique Authors" value={totalAuthors.toLocaleString()} badge="Global" badgeColor="text-[#001e4f] bg-blue-50" />
        <MetricCard icon="format_quote" label="Total Citations" value={totalCitations.toLocaleString()} badge="Citations" badgeColor="text-[#001e4f] bg-blue-50" />
        <MetricCard icon="star" label="Keywords Tracked" value={topKeywords.length.toString()} badge="Active" badgeColor="text-[#002626] bg-[#93f2f2]" />
      </div>

      {/* Visual Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-6 gap-8">
        {/* Publication Trends */}
        <div className="lg:col-span-4 bg-white rounded-xl p-8 shadow-sm">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h3 className="font-bold text-xl text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>Publication Trends</h3>
              <p className="text-sm text-[#43474e]">Annual publication count</p>
            </div>
          </div>
          <div className="h-64 flex items-end justify-between gap-4 px-2">
            {yearlyCounts.map((y, i) => (
              <div key={y.year} className={`flex-1 rounded-t-lg relative group transition-all hover:opacity-80 ${i === yearlyCounts.length - 1 ? "bg-[#001e4f]" : "bg-[#eceef0] hover:bg-[#00327a]"}`}
                style={{ height: `${(y.count / maxYearCount) * 100}%`, minHeight: 8 }}>
                <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-[#191c1e] text-white text-[10px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
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
        <div className="lg:col-span-2 bg-white rounded-xl p-8 shadow-sm">
          <h3 className="font-bold text-xl text-[#001e4f] mb-6" style={{fontFamily:"'Manrope',sans-serif"}}>Top Authors</h3>
          <div className="space-y-5">
            {topAuthors.slice(0, 5).map((a, i) => (
              <div key={i} className="flex items-center gap-4 group">
                <div className="text-sm font-bold text-slate-300">{String(i+1).padStart(2,"0")}</div>
                <div className="w-10 h-10 rounded-full bg-[#00327a] flex items-center justify-center text-white font-bold text-xs">
                  {a.name.split(",")[0]?.slice(0,2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-[#191c1e] truncate group-hover:text-[#001e4f] transition-colors">{a.name}</p>
                  <p className="text-[10px] text-slate-400">{a.citation_sum} citations</p>
                </div>
                <div className="text-xs font-bold text-[#003d3d] bg-[#93f2f2] px-2 py-1 rounded">{a.pub_count}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Network Preview */}
        <div className="lg:col-span-3 bg-white rounded-xl p-8 shadow-sm flex flex-col min-h-[400px]">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h3 className="font-bold text-xl text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>Network Preview</h3>
              <p className="text-sm text-[#43474e]">Co-authorship clustering</p>
            </div>
            <span className="material-symbols-outlined text-[#43474e]">hub</span>
          </div>
          <div className="flex-1 relative overflow-hidden rounded-xl bg-slate-50 border border-slate-100/50">
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="relative w-48 h-48">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-6 h-6 bg-[#001e4f] rounded-full" />
                <div className="absolute bottom-0 left-1/4 w-8 h-8 bg-[#003d3d] rounded-full" />
                <div className="absolute top-1/3 right-0 w-10 h-10 bg-[#00327a] rounded-full" />
                <div className="absolute top-1/2 left-0 w-4 h-4 bg-[#002626] rounded-full" />
                <svg className="absolute inset-0 w-full h-full stroke-slate-200 fill-none opacity-50" viewBox="0 0 100 100">
                  <line x1="50" y1="10" x2="25" y2="85" strokeWidth="0.5" />
                  <line x1="50" y1="10" x2="85" y2="40" strokeWidth="0.5" />
                  <line x1="25" y1="85" x2="85" y2="40" strokeWidth="0.5" />
                </svg>
              </div>
            </div>
            <div className="absolute bottom-4 left-4 right-4 bg-white/60 backdrop-blur-md p-3 rounded-lg border border-white/40">
              <p className="text-[10px] font-bold text-[#191c1e] uppercase tracking-wide">{topAuthors.length} Authors in Network</p>
              <p className="text-[10px] text-slate-500">Click to explore full network view</p>
            </div>
          </div>
        </div>

        {/* Top Keywords */}
        <div className="lg:col-span-3 bg-white rounded-xl p-8 shadow-sm">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h3 className="font-bold text-xl text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>Top Keywords</h3>
              <p className="text-sm text-[#43474e]">Most frequent terms</p>
            </div>
            <span className="material-symbols-outlined text-[#43474e]">label</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {topKeywords.slice(0, 20).map((k, i) => {
              const maxCount = topKeywords[0]?.count || 1;
              const opacity = 0.5 + (k.count / maxCount) * 0.5;
              return (
                <span key={i} className="px-3 py-1.5 bg-[#d5e3fc] text-[#001945] rounded-full text-xs font-bold" style={{ opacity }}>
                  {k.term} ({k.count})
                </span>
              );
            })}
          </div>
        </div>

        {/* Most Cited */}
        <div className="lg:col-span-6 bg-white rounded-xl p-8 shadow-sm">
          <h3 className="font-bold text-xl text-[#001e4f] mb-6" style={{fontFamily:"'Manrope',sans-serif"}}>Most Cited Publications</h3>
          <div className="space-y-4">
            {mostCited.slice(0, 5).map((c, i) => (
              <div key={i} className="flex items-start gap-4 group cursor-pointer">
                <span className="text-xs font-bold text-slate-300 mt-1">{String(i+1).padStart(2,"0")}</span>
                <div className="flex-1">
                  <h4 className="text-sm font-bold text-[#191c1e] leading-snug group-hover:text-[#001e4f] transition-colors">{c.title}</h4>
                  <p className="text-[11px] text-[#43474e] mt-1">{c.year} · PMID: {c.pmid}</p>
                </div>
                <div className="text-sm font-extrabold text-[#001e4f]">{c.citation_count}</div>
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
    <div className="p-6 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-4">
        <span className="text-slate-400 material-symbols-outlined">{icon}</span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badgeColor}`}>{badge}</span>
      </div>
      <p className="text-3xl font-extrabold text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>{value}</p>
      <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mt-1">{label}</p>
    </div>
  );
}
