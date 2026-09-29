"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import toast from "react-hot-toast";
import { exportApi } from "@/lib/api";
import { Button, Card, CardHeader, EmptyState, Icon, LoadingState, PageHeader, Skeleton, Tabs, type IconName, type TabItem } from "@/components/ui";

type DataFormat = "csv" | "ris" | "json";
type Tab = "data" | "methodology";

const TABS: TabItem<Tab>[] = [
  { value: "data", label: "Data export", icon: "table" },
  { value: "methodology", label: "Methodology & PRISMA", icon: "rule" },
];

const FORMAT_DETAILS: Record<DataFormat, { title: string; subtitle: string; icon: IconName; bullets: string[]; url: (id: number) => string }> = {
  csv: {
    title: "CSV — spreadsheet",
    subtitle: "Excel · Google Sheets · pandas · R",
    icon: "table",
    bullets: ["Complete metadata (PMID, DOI, authors, journal, year)", "Citation counts and keyword annotations", "Opens directly in Excel or Google Sheets"],
    url: exportApi.csvUrl,
  },
  ris: {
    title: "RIS — reference manager",
    subtitle: "Zotero · EndNote · Mendeley",
    icon: "book",
    bullets: ["Standard interchange format for reference managers", "Authors, abstract, keywords, DOI preserved", "Imports cleanly into Zotero, EndNote, Mendeley"],
    url: exportApi.risUrl,
  },
  json: {
    title: "JSON — programmatic",
    subtitle: "Versioned schema · scripts · notebooks",
    icon: "terminal",
    bullets: ["Every record with a `schema_version` field for pinning", "Analysis results included alongside publications", "Ideal for R, Python, or downstream tooling"],
    url: exportApi.jsonUrl,
  },
};

const INDIVIDUAL: Array<{ label: string; url: (id: number) => string }> = [
  { label: "CSV", url: exportApi.csvUrl },
  { label: "RIS", url: exportApi.risUrl },
  { label: "JSON", url: exportApi.jsonUrl },
  { label: "Methodology", url: exportApi.methodologyUrl },
  { label: "PRISMA", url: exportApi.prismaUrl },
];

export default function ExportManager() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const [activeTab, setActiveTab] = useState<Tab>("data");
  const [dataFormat, setDataFormat] = useState<DataFormat>("csv");
  const [methodologyText, setMethodologyText] = useState<string | null>(null);
  const [methodologyError, setMethodologyError] = useState(false);
  const [loadingMethodology, setLoadingMethodology] = useState(false);

  const loadMethodology = async () => {
    if (methodologyText) return;
    setLoadingMethodology(true);
    setMethodologyError(false);
    try {
      const response = await fetch(exportApi.methodologyUrl(projectId));
      if (!response.ok) throw new Error(`Methodology fetch failed with status ${response.status}`);
      setMethodologyText(await response.text());
    } catch {
      setMethodologyError(true);
      toast.error("Failed to load methodology log.");
    } finally {
      setLoadingMethodology(false);
    }
  };

  const handleTabChange = (next: Tab) => {
    setActiveTab(next);
    if (next === "methodology") loadMethodology();
  };

  const openDownload = (url: string) => {
    // noopener,noreferrer prevents the opened tab from navigating the parent
    // (tabnapping) and keeps the referrer out of the destination request.
    const newWindow = window.open(url, "_blank", "noopener,noreferrer");
    if (newWindow) newWindow.opener = null;
  };

  const handleDataExport = () => {
    openDownload(FORMAT_DETAILS[dataFormat].url(projectId));
    toast.success(`${dataFormat.toUpperCase()} download started`);
  };

  const details = FORMAT_DETAILS[dataFormat];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={`Step 4 · Export · Project #${projectId}`}
        title="Export your dataset"
        lede="Reference-manager files, spreadsheet exports, and the PRISMA-ready methodology log — everything a reproducible submission needs."
      >
        <Tabs items={TABS} value={activeTab} onChange={handleTabChange} ariaLabel="Export categories" />
      </PageHeader>

      {activeTab === "data" && (
        <section id="panel-data" role="tabpanel" aria-labelledby="tab-data" className="space-y-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <div className="lg:col-span-4">
              <p className="eyebrow mb-3">Format</p>
              <div role="radiogroup" aria-label="Export format" className="rule-t">
                {(Object.keys(FORMAT_DETAILS) as DataFormat[]).map((fmt) => {
                  const f = FORMAT_DETAILS[fmt];
                  const active = dataFormat === fmt;
                  return (
                    <button
                      key={fmt}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => setDataFormat(fmt)}
                      className={[
                        "w-full flex items-center gap-4 py-4 pr-3 pl-4 -ml-px border-l-2 rule-b text-left cursor-pointer",
                        "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
                        "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:-outline-offset-2 focus-visible:rounded-[var(--radius-sm)]",
                        active ? "border-l-primary bg-surface-raised" : "border-l-transparent hover:bg-surface-raised/70",
                      ].join(" ")}
                    >
                      <Icon name={f.icon} size={20} className={active ? "text-primary" : "text-on-surface-subtle"} />
                      <span className="flex-1 min-w-0">
                        <span className="block font-display text-lg text-on-surface leading-tight">{fmt.toUpperCase()}</span>
                        <span className="block text-xs text-on-surface-muted truncate">{f.subtitle}</span>
                      </span>
                      <span aria-hidden="true" className={`w-4 h-4 rounded-full border-2 ${active ? "border-primary bg-primary" : "border-outline-strong"}`} />
                    </button>
                  );
                })}
              </div>
            </div>

            <Card padding="lg" className="lg:col-span-8">
              <div className="flex flex-col md:flex-row gap-8 items-start">
                <div className="flex-1 space-y-5">
                  <div>
                    <p className="eyebrow mb-2">Selected format</p>
                    <h2 className="text-3xl text-on-surface leading-tight">{details.title}</h2>
                    <p className="mt-1.5 text-sm text-on-surface-muted">{details.subtitle}</p>
                  </div>
                  <ul className="space-y-2.5">
                    {details.bullets.map((b) => (
                      <li key={b} className="flex items-start gap-2.5 text-sm text-on-surface">
                        <Icon name="check" size={16} className="text-accent mt-0.5" />
                        {b}
                      </li>
                    ))}
                  </ul>
                  <div className="pt-2 flex flex-wrap items-center gap-4">
                    <Button onClick={handleDataExport} leadingIcon="download" size="lg">
                      Download {dataFormat.toUpperCase()}
                    </Button>
                    <a
                      href={exportApi.csvUrl(projectId)}
                      download
                      className="inline-flex items-center min-h-11 text-sm text-on-surface-muted underline underline-offset-4 decoration-outline hover:text-on-surface hover:decoration-on-surface focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2 rounded-[var(--radius-xs)]"
                    >
                      Quick-grab CSV →
                    </a>
                  </div>
                </div>
                <div className="hidden md:flex w-40 aspect-[3/4] rounded-[var(--radius-md)] border border-divider bg-surface items-center justify-center">
                  <Icon name={details.icon} size={56} strokeWidth={1.25} className="text-on-surface-subtle" />
                </div>
              </div>
            </Card>
          </div>

          <Card as="section" aria-labelledby="bundle-heading" className="border-l-4 border-l-accent">
            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-5">
              <div className="max-w-xl">
                <h2 id="bundle-heading" className="text-xl text-on-surface">
                  Everything in one click
                </h2>
                <p className="text-sm text-on-surface-muted mt-1.5 leading-relaxed">
                  One <code className="font-mono text-xs">.zip</code> with the CSV, RIS, JSON, methodology log, PRISMA SVG, and a manifest — drop it straight into your
                  supplementary materials.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button leadingIcon="archive" onClick={() => openDownload(exportApi.bundleUrl(projectId))}>
                  Download bundle
                </Button>
                <span className="text-xs text-on-surface-subtle hidden lg:inline px-1">or individually</span>
                {INDIVIDUAL.map((item) => (
                  <Button key={item.label} variant="outline" size="sm" leadingIcon="download" onClick={() => openDownload(item.url(projectId))}>
                    {item.label}
                  </Button>
                ))}
              </div>
            </div>
          </Card>
        </section>
      )}

      {activeTab === "methodology" && (
        <section id="panel-methodology" role="tabpanel" aria-labelledby="tab-methodology" className="space-y-8">
          <Card padding="lg">
            <CardHeader
              eyebrow="Supplementary file 1"
              title="Methodology log"
              subtitle="A complete record of every pipeline step — citable as supplementary material in your paper's Methods section."
              action={
                <Button leadingIcon="download" onClick={() => openDownload(exportApi.methodologyUrl(projectId))}>
                  Download .txt
                </Button>
              }
            />
            {loadingMethodology ? (
              <LoadingState label="Loading methodology log" className="space-y-3">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-11/12" />
                <Skeleton className="h-3 w-10/12" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-9/12" />
              </LoadingState>
            ) : methodologyText ? (
              <pre className="bg-code-bg text-code-fg font-mono text-xs rounded-[var(--radius-md)] p-6 overflow-x-auto whitespace-pre-wrap leading-relaxed border border-code-border">
                {methodologyText}
              </pre>
            ) : methodologyError ? (
              <EmptyState
                icon="alert"
                title="Couldn't load methodology log"
                description="The project may have been deleted, or the server is temporarily unavailable. Switch tabs and back to retry."
              />
            ) : (
              <EmptyState
                icon="searchOff"
                title="No methodology data yet"
                description="Run a search from the Search tab — once records are fetched, every pipeline step is recorded here."
              />
            )}
          </Card>

          <Card padding="lg">
            <CardHeader
              eyebrow="Supplementary figure 1"
              title="PRISMA 2020 flow diagram"
              subtitle="Self-contained SVG of identified → screened → included counts per data source. Scales cleanly for journal print at any size."
              action={
                <Button leadingIcon="download" onClick={() => openDownload(exportApi.prismaUrl(projectId))}>
                  Download .svg
                </Button>
              }
            />
            <div className="border border-divider rounded-[var(--radius-md)] overflow-hidden bg-surface-raised">
              <object data={exportApi.prismaUrl(projectId)} type="image/svg+xml" aria-label="PRISMA 2020 flow diagram preview" className="w-full h-[520px]" />
            </div>
          </Card>
        </section>
      )}

      {TABS.filter((tab) => tab.value !== activeTab).map((tab) => (
        <div key={tab.value} id={`panel-${tab.value}`} role="tabpanel" aria-labelledby={`tab-${tab.value}`} hidden />
      ))}
    </div>
  );
}
