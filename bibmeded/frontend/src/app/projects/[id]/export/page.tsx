"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { exportApi } from "@/lib/api";
import toast from "react-hot-toast";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Skeleton,
  Tabs,
  type TabItem,
} from "@/components/ui";

type DataFormat = "csv" | "ris";
type Tab = "data" | "methodology";

const TABS: TabItem<Tab>[] = [
  { value: "data", label: "Data export", icon: "table_chart" },
  { value: "methodology", label: "Methodology & PRISMA", icon: "rule" },
];

const FORMAT_DETAILS: Record<
  DataFormat,
  { title: string; subtitle: string; icon: string; bullets: string[] }
> = {
  csv: {
    title: "CSV — spreadsheet",
    subtitle: "Excel · Google Sheets · pandas · R",
    icon: "table_chart",
    bullets: [
      "Complete metadata (PMID, DOI, authors, journal, year)",
      "Citation counts and keyword annotations",
      "Excel / Google Sheets compatible",
    ],
  },
  ris: {
    title: "RIS — reference manager",
    subtitle: "Zotero · EndNote · Mendeley",
    icon: "menu_book",
    bullets: [
      "Standard interchange format for reference managers",
      "Authors, abstract, keywords, DOI preserved",
      "Imports cleanly into Zotero, EndNote, Mendeley",
    ],
  },
};

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
      if (!response.ok) {
        throw new Error(`Methodology fetch failed with status ${response.status}`);
      }
      const text = await response.text();
      setMethodologyText(text);
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
    // Always open with noopener,noreferrer — prevents the opened tab from navigating
    // the parent (tabnapping) and keeps the referrer out of the destination request.
    const newWindow = window.open(url, "_blank", "noopener,noreferrer");
    if (newWindow) newWindow.opener = null;
  };

  const handleDataExport = () => {
    const url = dataFormat === "csv" ? exportApi.csvUrl(projectId) : exportApi.risUrl(projectId);
    openDownload(url);
    toast.success(`${dataFormat.toUpperCase()} download started`);
  };

  const details = FORMAT_DETAILS[dataFormat];

  return (
    <div className="py-10 space-y-10">
      <header className="space-y-3">
        <div className="flex items-center gap-3">
          <Badge tone="primary">Step 4 · Export</Badge>
          <span className="text-xs text-on-surface-subtle">Project #{projectId}</span>
        </div>
        <h1
          className="text-4xl md:text-5xl font-extrabold text-primary tracking-tight"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Export your dataset
        </h1>
        <p className="text-on-surface-muted text-base md:text-lg max-w-2xl leading-relaxed">
          Reference-manager files, spreadsheet exports, and the PRISMA-ready methodology log — everything you need for a reproducible submission.
        </p>
        <div className="pt-2">
          <Tabs items={TABS} value={activeTab} onChange={handleTabChange} ariaLabel="Export categories" />
        </div>
      </header>

      {activeTab === "data" && (
        <section id="panel-data" role="tabpanel" aria-labelledby="tab-data" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card padding="lg" className="lg:col-span-2">
              <div className="flex flex-col md:flex-row gap-8 items-start">
                <div className="flex-1 space-y-5">
                  <Badge tone="success" size="md">
                    <span className="material-symbols-outlined mr-1" aria-hidden="true" style={{ fontSize: "0.95em" }}>
                      auto_awesome
                    </span>
                    Recommended for analysis
                  </Badge>
                  <div>
                    <h2
                      className="text-3xl font-bold text-on-surface leading-tight"
                      style={{ fontFamily: "var(--font-display)" }}
                    >
                      {details.title}
                    </h2>
                    <p className="mt-1 text-sm text-on-surface-muted">{details.subtitle}</p>
                  </div>
                  <ul className="space-y-2.5" role="list">
                    {details.bullets.map((b) => (
                      <li key={b} className="flex items-start gap-2.5 text-sm text-on-surface">
                        <span
                          className="material-symbols-outlined text-success flex-shrink-0 mt-0.5"
                          aria-hidden="true"
                          style={{ fontSize: "1.15em", fontVariationSettings: "'FILL' 1" }}
                        >
                          check_circle
                        </span>
                        {b}
                      </li>
                    ))}
                  </ul>
                  <div className="pt-2 flex flex-wrap items-center gap-3">
                    <Button onClick={handleDataExport} leadingIcon="download" size="lg">
                      Download {dataFormat.toUpperCase()}
                    </Button>
                    <a
                      href={exportApi.csvUrl(projectId)}
                      download
                      className="text-sm text-on-surface-muted underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2 rounded-sm"
                    >
                      Quick-grab CSV →
                    </a>
                  </div>
                </div>
                <div className="hidden md:flex w-48 aspect-[3/4] bg-surface-sunken rounded-[var(--radius-lg)] items-center justify-center">
                  <span
                    className="material-symbols-outlined text-on-surface-subtle"
                    aria-hidden="true"
                    style={{ fontSize: "72px" }}
                  >
                    {details.icon}
                  </span>
                </div>
              </div>
            </Card>

            <Card padding="md">
              <h3
                className="text-sm font-bold uppercase tracking-[0.14em] text-on-surface-subtle mb-4"
                style={{ fontFamily: "var(--font-display)" }}
              >
                Format
              </h3>
              <div role="radiogroup" aria-label="Export format" className="space-y-2">
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
                        "w-full flex items-center gap-3 p-3 rounded-[var(--radius-md)]",
                        "border text-left cursor-pointer",
                        "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
                        "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
                        active
                          ? "border-primary bg-primary-container/60"
                          : "border-divider hover:bg-surface-hover",
                      ].join(" ")}
                    >
                      <span
                        className="material-symbols-outlined text-primary"
                        aria-hidden="true"
                        style={{ fontSize: "1.4em" }}
                      >
                        {f.icon}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="block text-sm font-bold text-on-surface">{fmt.toUpperCase()}</span>
                        <span className="block text-xs text-on-surface-muted truncate">{f.subtitle}</span>
                      </span>
                      <span
                        aria-hidden="true"
                        className={[
                          "w-4 h-4 rounded-full border-2 transition-colors",
                          active ? "border-primary bg-primary" : "border-outline",
                        ].join(" ")}
                      />
                    </button>
                  );
                })}
              </div>
              <p className="mt-4 text-xs text-on-surface-muted leading-relaxed">
                Switching format updates the call-to-action on the left.
              </p>
            </Card>
          </div>

          <Card padding="md" className="border-l-4 border-l-accent">
            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
              <div>
                <h3
                  className="text-base font-bold text-on-surface"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  Want everything in one click?
                </h3>
                <p className="text-sm text-on-surface-muted mt-1">
                  One <code className="font-mono text-xs">.zip</code> with the CSV, RIS, methodology log, PRISMA SVG, and a manifest — drop straight into your submission.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button leadingIcon="folder_zip" onClick={() => openDownload(exportApi.bundleUrl(projectId))}>
                  Download bundle
                </Button>
                <span className="text-xs text-on-surface-subtle hidden lg:inline">or grab individually:</span>
                <Button variant="outline" size="sm" leadingIcon="download" onClick={() => openDownload(exportApi.csvUrl(projectId))}>
                  CSV
                </Button>
                <Button variant="outline" size="sm" leadingIcon="download" onClick={() => openDownload(exportApi.risUrl(projectId))}>
                  RIS
                </Button>
                <Button variant="outline" size="sm" leadingIcon="download" onClick={() => openDownload(exportApi.jsonUrl(projectId))}>
                  JSON
                </Button>
                <Button variant="outline" size="sm" leadingIcon="download" onClick={() => openDownload(exportApi.methodologyUrl(projectId))}>
                  Methodology
                </Button>
                <Button variant="outline" size="sm" leadingIcon="download" onClick={() => openDownload(exportApi.prismaUrl(projectId))}>
                  PRISMA
                </Button>
              </div>
            </div>
          </Card>
        </section>
      )}

      {activeTab === "methodology" && (
        <section
          id="panel-methodology"
          role="tabpanel"
          aria-labelledby="tab-methodology"
          className="space-y-6"
        >
          <Card padding="lg">
            <CardHeader
              title="Methodology log"
              subtitle="A complete record of every pipeline step — citable as supplementary material in your paper's Methods section."
              action={
                <Button leadingIcon="download" onClick={() => openDownload(exportApi.methodologyUrl(projectId))}>
                  Download .txt
                </Button>
              }
            />
            {loadingMethodology ? (
              <div className="space-y-3" aria-live="polite" aria-busy="true">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-11/12" />
                <Skeleton className="h-3 w-10/12" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-9/12" />
              </div>
            ) : methodologyText ? (
              <pre className="bg-code-bg text-code-fg font-mono text-xs rounded-[var(--radius-md)] p-6 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {methodologyText}
              </pre>
            ) : methodologyError ? (
              <EmptyState
                icon="error"
                title="Couldn't load methodology log"
                description="The project may have been deleted, or the server is temporarily unavailable. Switch tabs and back to retry."
              />
            ) : (
              <EmptyState
                icon="search_off"
                title="No methodology data yet"
                description="Run a search from the Search tab — once records are fetched, every pipeline step is recorded here."
              />
            )}
          </Card>

          <Card padding="lg">
            <CardHeader
              title="PRISMA 2020 flow diagram"
              subtitle="Self-contained SVG of identified → screened → included counts per data source. Drop it straight into supplementary materials — scales for journal print at any size."
              action={
                <Button leadingIcon="download" onClick={() => openDownload(exportApi.prismaUrl(projectId))}>
                  Download .svg
                </Button>
              }
            />
            <div className="border border-divider rounded-[var(--radius-md)] overflow-hidden bg-surface-sunken">
              <object
                data={exportApi.prismaUrl(projectId)}
                type="image/svg+xml"
                aria-label="PRISMA 2020 flow diagram preview"
                className="w-full h-[520px]"
              />
            </div>
          </Card>
        </section>
      )}
      {TABS.filter((tab) => tab.value !== activeTab).map((tab) => (
        <div
          key={tab.value}
          id={`panel-${tab.value}`}
          role="tabpanel"
          aria-labelledby={`tab-${tab.value}`}
          hidden
        />
      ))}
    </div>
  );
}
