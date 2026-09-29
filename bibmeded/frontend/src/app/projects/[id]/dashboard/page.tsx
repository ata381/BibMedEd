"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { analysisApi, projectsApi, Project } from "@/lib/api";
import { ForceGraph } from "@/components/force-graph";
import { BarChart } from "@/components/charts/bar-chart";
import { RankedBars } from "@/components/charts/ranked-bars";
import { Button, Card, CardHeader, EmptyState, Icon, Stat, StatRow, Tabs, type TabItem } from "@/components/ui";

type AnalysisData = Record<string, unknown>;
type DashboardTab = "overview" | "authors" | "networks" | "citations";

const ANALYSIS_TYPES = ["publications", "authors", "countries", "keywords", "citations", "journals"];
const TABS: TabItem<DashboardTab>[] = [
  { value: "overview", label: "Overview" },
  { value: "authors", label: "Authors" },
  { value: "networks", label: "Networks" },
  { value: "citations", label: "Citations" },
];
const TOP_N = 8;
const KEYWORD_LIMIT = 24;

interface YearCount {
  year: number;
  count: number;
}
interface TopAuthor {
  name: string;
  pub_count: number;
  citation_sum: number;
}
interface CitedPublication {
  title: string;
  pmid: string;
  year: number;
  citation_count: number;
}
interface Keyword {
  term: string;
  count: number;
}
interface Named {
  name?: string;
  country?: string;
  count: number;
}
interface RawNetwork {
  nodes: Array<{ id: string | number; label?: string; size?: number; name?: string; pub_count?: number }>;
  links: Array<{ source: string | number; target: string | number; weight?: number }>;
}

function normaliseNetwork(raw: RawNetwork | undefined) {
  const network = raw ?? { nodes: [], links: [] };
  return {
    nodes: network.nodes.map((node) => ({
      id: String(node.id),
      label: node.label ?? node.name ?? String(node.id),
      size: node.size ?? node.pub_count ?? 1,
    })),
    links: network.links.map((link) => ({ source: String(link.source), target: String(link.target), weight: link.weight })),
  };
}

export default function Dashboard() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [project, setProject] = useState<Project | null>(null);
  const [analyses, setAnalyses] = useState<Record<string, AnalysisData>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Abort controller so a slow analysis chain for a previously-viewed
    // project can't resolve after navigation and clobber the current one.
    const ctrl = new AbortController();
    const load = async () => {
      try {
        const proj = await projectsApi.get(projectId);
        if (ctrl.signal.aborted) return;
        setProject(proj.data);
        const results: Record<string, AnalysisData> = {};
        for (const t of ANALYSIS_TYPES) {
          if (ctrl.signal.aborted) return;
          try {
            const r = await analysisApi.get(projectId, t);
            results[t] = r.data.results as AnalysisData;
          } catch {
            try {
              const r = await analysisApi.run(projectId, t);
              results[t] = r.data.results as AnalysisData;
            } catch {}
          }
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

  if (loading) {
    return (
      <div role="status" aria-live="polite" className="flex items-center justify-center h-[60vh] gap-3 text-on-surface-muted">
        <Icon name="loader" size={20} className="animate-spin" />
        Running all analyses…
      </div>
    );
  }

  const pub = analyses.publications || {};
  const auth = analyses.authors || {};
  const cite = analyses.citations || {};
  const kw = analyses.keywords || {};
  const yearlyCounts = (pub.yearly_counts as YearCount[]) || [];
  const topAuthors = (auth.top_authors as TopAuthor[]) || [];
  const mostCited = (cite.most_cited as CitedPublication[]) || [];
  const topKeywords = (kw.top_keywords as Keyword[]) || [];
  const topJournals = ((analyses.journals?.top_journals as Named[]) || []).map((j) => ({ label: j.name ?? "Unknown", value: j.count }));
  const countries = ((analyses.countries?.countries as Named[]) || []).map((c) => ({ label: c.country ?? "Unknown", value: c.count }));
  const coauthorNetwork = normaliseNetwork(auth.coauthorship_network as RawNetwork | undefined);
  const totalPubs = (pub.total as number) || 0;
  const totalAuthors = (auth.total_authors as number) || 0;
  const totalCitations = (cite.total_citations as number) || 0;
  const yearSpan = yearlyCounts.length ? `${yearlyCounts[0].year}–${yearlyCounts[yearlyCounts.length - 1].year}` : "—";

  if (totalPubs === 0) {
    return (
      <div className="space-y-8">
        <PageTitle project={project} />
        <Card>
          <EmptyState
            icon="chart"
            title="No publications to analyze"
            description="Run a search first to populate results, then come back here for analysis."
            action={<Button onClick={() => router.push(`/projects/${projectId}/search`)}>Go to Search</Button>}
          />
        </Card>
      </div>
    );
  }

  const show = (...tabs: DashboardTab[]) => tabs.includes(activeTab);

  return (
    <div className="space-y-8">
      <PageTitle project={project} />

      <Tabs items={TABS} value={activeTab} onChange={setActiveTab} ariaLabel="Dashboard sections" />

      <section id={`panel-${activeTab}`} role="tabpanel" aria-labelledby={`tab-${activeTab}`} className="space-y-8">
        {show("overview") && (
          <StatRow ariaLabel="Corpus summary">
            <Stat label="Publications" value={totalPubs.toLocaleString()} note={`Included records, ${yearSpan}`} />
            <Stat label="Unique authors" value={totalAuthors.toLocaleString()} note="After name normalisation" />
            <Stat label="Total citations" value={totalCitations.toLocaleString()} note="Sum across included records" />
            <Stat label="Keywords tracked" value={topKeywords.length.toString()} note="Distinct indexed terms" />
          </StatRow>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-6 gap-6">
          {show("overview") && (
            <Card as="section" className="lg:col-span-4" aria-labelledby="fig-trends">
              <CardHeader eyebrow="Figure 1" title={<span id="fig-trends">Publication trends</span>} subtitle="Annual publication count across the included corpus." />
              <BarChart data={yearlyCounts.map((y) => ({ label: String(y.year), value: y.count }))} ariaLabel="Annual publication counts" />
            </Card>
          )}

          {show("overview", "authors") && (
            <Card as="section" className={activeTab === "authors" ? "lg:col-span-3" : "lg:col-span-2"} aria-labelledby="table-authors">
              <CardHeader eyebrow="Table 1" title={<span id="table-authors">Top authors</span>} subtitle="Ranked by publications in the corpus." />
              <RankedBars
                data={topAuthors.slice(0, TOP_N).map((a) => ({ label: a.name, value: a.pub_count, note: `${a.citation_sum.toLocaleString()} citations` }))}
                valueLabel="publications"
              />
            </Card>
          )}

          {show("authors") && countries.length > 0 && (
            <Card as="section" className="lg:col-span-3" aria-labelledby="table-countries">
              <CardHeader eyebrow="Table 2" title={<span id="table-countries">Countries</span>} subtitle="Affiliation country of contributing authors." />
              <RankedBars data={countries.slice(0, TOP_N)} valueLabel="publications" />
            </Card>
          )}

          {show("overview", "networks", "authors") && (
            <Card as="section" padding="none" className="lg:col-span-3 flex flex-col min-h-[440px] overflow-hidden" aria-labelledby="fig-network">
              <div className="p-5 md:p-6 pb-0">
                <CardHeader eyebrow="Figure 2" title={<span id="fig-network">Network preview</span>} subtitle="Co-authorship clustering." className="mb-3" />
              </div>
              <div className="flex-1 relative bg-surface-sunken border-t border-divider">
                <ForceGraph nodes={coauthorNetwork.nodes} links={coauthorNetwork.links} />
              </div>
            </Card>
          )}

          {show("overview", "networks") && (
            <Card as="section" className="lg:col-span-3" aria-labelledby="table-keywords">
              <CardHeader eyebrow="Table 3" title={<span id="table-keywords">Top keywords</span>} subtitle="Most frequent indexed terms." />
              <KeywordCloud keywords={topKeywords.slice(0, KEYWORD_LIMIT)} />
            </Card>
          )}

          {show("overview", "citations") && (
            <Card as="section" className="lg:col-span-4" aria-labelledby="table-cited">
              <CardHeader eyebrow="Table 4" title={<span id="table-cited">Most cited publications</span>} subtitle="Citation counts as reported by the source database." />
              <ol className="divide-y divide-divider">
                {mostCited.slice(0, TOP_N).map((c, i) => (
                  <li key={`${c.pmid}-${i}`} className="grid grid-cols-[2rem_1fr_auto] gap-x-4 py-3.5 items-start">
                    <span className="numeral text-sm text-on-surface-subtle pt-1">{String(i + 1).padStart(2, "0")}</span>
                    <div className="min-w-0">
                      <h3 className="text-base leading-snug text-on-surface">{c.title}</h3>
                      <p className="text-xs text-on-surface-subtle mt-1 tabular-nums">
                        {c.year} · PMID {c.pmid}
                      </p>
                    </div>
                    <span className="numeral text-xl text-on-surface tabular-nums">
                      {c.citation_count}
                      <span className="sr-only"> citations</span>
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          )}

          {show("overview", "citations") && topJournals.length > 0 && (
            <Card as="section" className="lg:col-span-2" aria-labelledby="table-journals">
              <CardHeader eyebrow="Table 5" title={<span id="table-journals">Top journals</span>} subtitle="Venues publishing the corpus." />
              <RankedBars data={topJournals.slice(0, TOP_N)} valueLabel="publications" />
            </Card>
          )}
        </div>
      </section>

      {TABS.filter((tab) => tab.value !== activeTab).map((tab) => (
        <div key={tab.value} id={`panel-${tab.value}`} role="tabpanel" aria-labelledby={`tab-${tab.value}`} hidden />
      ))}
    </div>
  );
}

function PageTitle({ project }: { project: Project | null }) {
  return (
    <header className="pt-2 pb-6 rule-b">
      <p className="eyebrow mb-3">Step 3 · Analysis</p>
      <h1 className="text-3xl md:text-4xl text-on-surface leading-[1.05]">Analysis overview</h1>
      {project ? (
        <p className="mt-3 text-lg text-on-surface-muted font-display italic">{project.name}</p>
      ) : null}
    </header>
  );
}

function KeywordCloud({ keywords }: { keywords: Keyword[] }) {
  const maxCount = keywords[0]?.count || 1;
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Top keywords">
      {keywords.map((k) => {
        const weight = k.count / maxCount;
        const strong = weight > 0.66;
        return (
          <li
            key={k.term}
            className={`inline-flex items-baseline gap-1.5 rounded-[var(--radius-sm)] border px-2.5 py-1 ${
              strong ? "bg-primary-container border-transparent text-on-primary-container" : "border-divider text-on-surface"
            }`}
            style={{ fontSize: `${0.8125 + weight * 0.3}rem` }}
          >
            <span className="font-display">{k.term}</span>
            <span className="text-xs font-sans text-on-surface-subtle tabular-nums">{k.count}</span>
          </li>
        );
      })}
    </ul>
  );
}
