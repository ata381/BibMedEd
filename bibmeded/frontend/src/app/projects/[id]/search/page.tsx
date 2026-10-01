"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { searchApi, adaptersApi, AdapterInfo } from "@/lib/api";
import { fetchReadOnly, useReadOnly } from "@/lib/read-only";
import { Button, ConfirmDialog, Icon, PageHeader } from "@/components/ui";

const MAX_RESULTS = 2000;
const POLL_INTERVAL_MS = 2000;
const REDIRECT_DELAY_MS = 500;
const PUBMED_TAGS = ["[Mesh]", "[tiab]", "[PDAT]", "[AU]", "[TA]"];
const OPERATORS = ["AND", "OR", "NOT"];

const CHIP_CLASSES = (active: boolean) =>
  [
    "inline-flex items-center min-h-10 px-4 rounded-[var(--radius-md)] text-sm font-semibold border cursor-pointer",
    "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
    "peer-focus-visible:outline-2 peer-focus-visible:outline-[color:var(--color-focus-ring)] peer-focus-visible:outline-offset-2",
    active
      ? "bg-ink text-on-ink border-ink"
      : "bg-surface-raised text-on-surface-muted border-outline-strong hover:text-on-surface hover:border-on-surface",
  ].join(" ");

const MODE_CLASSES = (active: boolean) =>
  [
    "inline-flex items-center gap-2 h-11 px-2 -mb-px border-b-2 text-sm font-semibold cursor-pointer",
    "transition-colors duration-[var(--duration-fast)]",
    "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:-outline-offset-2 focus-visible:rounded-[var(--radius-sm)]",
    active ? "border-on-surface text-on-surface" : "border-transparent text-on-surface-muted hover:text-on-surface",
  ].join(" ");

export default function SearchConfig() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);
  const [topicA, setTopicA] = useState('"Artificial Intelligence" OR "AI" OR "Machine Learning"');
  const [topicB, setTopicB] = useState('"Medical Education" OR "Curriculum"');
  const [operator, setOperator] = useState("AND");
  const [yearStart, setYearStart] = useState("2022");
  const [yearEnd, setYearEnd] = useState("2025");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ found: number; fetched: number; total: number } | null>(null);
  const [advancedMode, setAdvancedMode] = useState(false);
  const readOnly = useReadOnly() !== false;
  const [rawQuery, setRawQuery] = useState("");
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [source, setSource] = useState("pubmed");

  // PubMed uses field tags like [PDAT]; OpenAlex and others use plain text search.
  const pubmedQuery = `(${topicA}) ${operator} (${topicB}) AND ("${yearStart}/01/01"[PDAT] : "${yearEnd}/12/31"[PDAT])`;
  const genericQuery = `(${topicA}) ${operator} (${topicB})`;
  const builtQuery = source === "pubmed" ? pubmedQuery : genericQuery;
  const queryString = advancedMode ? rawQuery : builtQuery;
  const sourceName = adapters.find((a) => a.name === source)?.display_name || source;

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const redirectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  // The App Router does not remount this page when only `[id]` changes, so a
  // search started on a previous project must stop polling/redirecting here.
  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
      if (pollRef.current) clearInterval(pollRef.current);
      if (redirectTimeoutRef.current) clearTimeout(redirectTimeoutRef.current);
    };
  }, [projectId]);

  useEffect(() => {
    adaptersApi.list().then((res) => setAdapters(res.data)).catch(() => {});
  }, []);

  const handleSearch = useCallback(async () => {
    if (await fetchReadOnly()) return;
    setLoading(true);
    setStatus("Submitting search...");
    try {
      const res = await searchApi.trigger(projectId, queryString, source, yearStart, yearEnd);
      if (cancelledRef.current) return;
      const queryId = res.data.query_id;
      setStatus("Search dispatched...");
      setProgress(null);
      if (pollRef.current) clearInterval(pollRef.current);
      if (redirectTimeoutRef.current) clearTimeout(redirectTimeoutRef.current);
      pollRef.current = setInterval(async () => {
        if (cancelledRef.current) return;
        try {
          const s = await searchApi.status(projectId, queryId);
          if (cancelledRef.current) return;
          const found = s.data.raw_result_count ?? 0;
          const fetched = s.data.result_count ?? 0;
          if (found > 0 && fetched === 0) {
            setStatus(`Found ${found.toLocaleString()} records. Fetching...`);
            setProgress({ found, fetched: 0, total: Math.min(found, MAX_RESULTS) });
          } else if (found > 0 && fetched > 0) {
            const total = Math.min(found, MAX_RESULTS);
            setStatus(`Fetched ${fetched.toLocaleString()} of ${total.toLocaleString()} records...`);
            setProgress({ found, fetched, total });
          }
          if (s.data.status === "completed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setProgress({ found, fetched, total: fetched });
            toast.success(`${fetched.toLocaleString()} publications ready.`);
            redirectTimeoutRef.current = setTimeout(() => {
              if (cancelledRef.current) return;
              router.push(`/projects/${projectId}/results`);
            }, REDIRECT_DELAY_MS);
          } else if (s.data.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setStatus("Search failed.");
            setProgress(null);
            setLoading(false);
            toast.error("Search failed. Please try again.");
          }
        } catch {
          if (cancelledRef.current) return;
          if (pollRef.current) clearInterval(pollRef.current);
          setStatus("Error polling status.");
          setProgress(null);
          setLoading(false);
          toast.error("Lost connection while checking search status.");
        }
      }, POLL_INTERVAL_MS);
    } catch {
      if (cancelledRef.current) return;
      setStatus("Failed to start search.");
      setLoading(false);
      toast.error("Could not start search. Is the backend running?");
    }
  }, [projectId, queryString, source, yearStart, yearEnd, router]);

  const [confirmDiscardRaw, setConfirmDiscardRaw] = useState(false);

  const switchToBuilder = () => {
    if (advancedMode && rawQuery && rawQuery !== builtQuery) {
      setConfirmDiscardRaw(true);
      return;
    }
    setAdvancedMode(false);
  };

  const switchToRaw = () => {
    if (advancedMode) return;
    setAdvancedMode(true);
    setRawQuery(builtQuery);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Step 1 · Search strategy"
        title="Search strategy"
        lede="Compose a Boolean query with field tags, pick a database, and run it. Every parameter — including the exact query string — is written to the methodology log."
      />

      <div role="group" aria-label="Query mode" className="flex items-end gap-6 border-b border-divider">
        <button type="button" onClick={switchToBuilder} aria-pressed={!advancedMode} className={MODE_CLASSES(!advancedMode)}>
          <Icon name="sliders" size={16} />
          Query Builder
        </button>
        <button type="button" onClick={switchToRaw} aria-pressed={advancedMode} className={MODE_CLASSES(advancedMode)}>
          <Icon name="terminal" size={16} />
          Advanced Query (Raw)
        </button>
      </div>

      <ConfirmDialog
        open={confirmDiscardRaw}
        tone="danger"
        title="Discard raw query edits?"
        description={
          <p>
            The Query Builder regenerates the query from its fields, so your hand-edited raw query will be lost. Copy it first if you
            want to keep it.
          </p>
        }
        confirmLabel="Discard edits"
        cancelLabel="Keep editing"
        onConfirm={() => {
          setConfirmDiscardRaw(false);
          setAdvancedMode(false);
        }}
        onCancel={() => setConfirmDiscardRaw(false)}
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        <div className="lg:col-span-7 space-y-10">
          {advancedMode ? (
            <Section number="01" title="Raw query">
              <p className="text-sm text-on-surface-muted mb-4 max-w-prose">
                {source === "pubmed"
                  ? "Paste or write your full PubMed/MEDLINE query with MeSH terms, field tags, and Boolean operators."
                  : `Enter your search query for ${sourceName}. Use plain text keywords and Boolean operators.`}
              </p>
              <label htmlFor="raw-query" className="sr-only">
                Raw query
              </label>
              <textarea
                id="raw-query"
                value={rawQuery}
                onChange={(e) => setRawQuery(e.target.value)}
                rows={8}
                placeholder={'(Education, Medical[Mesh] OR "medical education"[tiab]) AND (Artificial Intelligence[Mesh] OR AI[tiab]) AND ("2020"[Date - Publication] : "3000"[Date - Publication])'}
                className="field field-code resize-y"
              />
              <div className="mt-4 flex gap-2 flex-wrap items-center">
                <span className="eyebrow mr-1">Insert tag</span>
                {PUBMED_TAGS.map((tag) => (
                  <button
                    type="button"
                    key={tag}
                    onClick={() => setRawQuery((q) => q + tag)}
                    className="min-h-8 px-2.5 font-mono text-xs font-semibold rounded-[var(--radius-sm)] border border-outline-strong text-on-surface hover:bg-surface-hover cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
                  >
                    {tag}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setRawQuery("")}
                  className="ml-auto min-h-8 px-3 text-xs font-semibold rounded-[var(--radius-sm)] text-danger hover:bg-danger-container cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
                >
                  Clear text
                </button>
              </div>
            </Section>
          ) : (
            <>
              <Section number="01" title="Research topics">
                <div className="space-y-4">
                  <div>
                    <label htmlFor="topic-a" className="block text-sm font-semibold text-on-surface mb-2">
                      Topic A
                    </label>
                    <input id="topic-a" value={topicA} onChange={(e) => setTopicA(e.target.value)} className="field font-mono text-sm" />
                  </div>
                  <div role="radiogroup" aria-label="Boolean operator" className="flex items-center gap-2 pl-1">
                    <span aria-hidden="true" className="h-px w-6 bg-outline-strong" />
                    {OPERATORS.map((op) => (
                      <label key={op} className="cursor-pointer">
                        <input
                          type="radio"
                          name="boolean-operator"
                          value={op}
                          checked={operator === op}
                          onChange={() => setOperator(op)}
                          className="peer sr-only"
                        />
                        <span className={`${CHIP_CLASSES(operator === op)} min-h-9 px-3 font-mono text-xs`}>{op}</span>
                      </label>
                    ))}
                  </div>
                  <div>
                    <label htmlFor="topic-b" className="block text-sm font-semibold text-on-surface mb-2">
                      Topic B
                    </label>
                    <input id="topic-b" value={topicB} onChange={(e) => setTopicB(e.target.value)} className="field font-mono text-sm" />
                  </div>
                </div>
              </Section>

              <Section number="02" title="Publication years">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 max-w-lg">
                  <YearField id="year-start" label="Start year" value={yearStart} onChange={setYearStart} />
                  <YearField id="year-end" label="End year" value={yearEnd} onChange={setYearEnd} />
                </div>
              </Section>

              {adapters.length > 1 && (
                <Section number="03" title="Data source">
                  <div role="radiogroup" aria-label="Data source" className="flex gap-2 flex-wrap">
                    {adapters.map((a) => (
                      <label key={a.name} className="cursor-pointer">
                        <input
                          type="radio"
                          name="data-source"
                          value={a.name}
                          checked={source === a.name}
                          onChange={() => setSource(a.name)}
                          className="peer sr-only"
                        />
                        <span className={CHIP_CLASSES(source === a.name)}>
                          {a.display_name}
                          {a.requires_api_key && <span className="ml-1.5 text-xs font-normal opacity-80">(API key)</span>}
                        </span>
                      </label>
                    ))}
                  </div>
                </Section>
              )}
            </>
          )}
        </div>

        <div className="lg:col-span-5">
          <div className="bg-ink text-on-ink rounded-[var(--radius-lg)] p-6 md:p-7 lg:sticky lg:top-8 elev-3">
            <div className="flex items-center justify-between gap-3 mb-5">
              <h2 className="text-xl text-on-ink">Query preview</h2>
              <span className="text-xs text-on-ink-muted">{sourceName}</span>
            </div>
            <div className="bg-code-bg text-code-fg font-mono text-xs leading-relaxed rounded-[var(--radius-md)] p-4 border border-code-border whitespace-pre-wrap break-words">
              {advancedMode ? (
                rawQuery || <span className="text-code-muted italic">Enter your raw query...</span>
              ) : source === "pubmed" ? (
                <>
                  ({topicA}) <span className="text-secondary font-bold">{operator}</span> ({topicB}){" "}
                  <span className="text-secondary font-bold">AND</span> (&quot;{yearStart}/01/01&quot;[PDAT] : &quot;{yearEnd}/12/31&quot;[PDAT])
                </>
              ) : (
                <>
                  ({topicA}) <span className="text-secondary font-bold">{operator}</span> ({topicB})
                  <br />
                  <span className="text-code-muted">+ date filter: {yearStart}–{yearEnd}</span>
                </>
              )}
            </div>
            <p className="mt-3 text-xs text-on-ink-muted">
              Up to {MAX_RESULTS.toLocaleString()} records per run. The results page warns if the database returned more.
            </p>
            {status && (
              <div className="mt-5" role="status" aria-live="polite" aria-atomic="true">
                <div className="flex items-center gap-2 text-sm text-on-ink mb-2">
                  {loading && <Icon name="loader" size={15} className="animate-spin" />}
                  {status}
                </div>
                {progress && progress.total > 0 && (
                  <div
                    role="progressbar"
                    aria-label="Search records fetched"
                    aria-valuemin={0}
                    aria-valuemax={progress.total}
                    aria-valuenow={progress.fetched}
                    className="w-full bg-on-ink/20 rounded-full h-1.5 overflow-hidden"
                  >
                    <div
                      className="bg-secondary h-full rounded-full transition-[width] duration-500"
                      style={{ width: `${Math.min(100, Math.round((progress.fetched / progress.total) * 100))}%` }}
                    />
                  </div>
                )}
              </div>
            )}
            <Button
              variant="secondary"
              size="lg"
              fullWidth
              className="mt-6"
              onClick={handleSearch}
              disabled={loading || readOnly}
              loading={loading}
              trailingIcon="arrowRight"
            >
              {loading ? "Searching..." : "Execute Search"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ number, title, children }: { number: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={`section-${number}`} className="grid grid-cols-[3rem_1fr] gap-x-4">
      <span aria-hidden="true" className="numeral text-2xl text-primary pt-0.5">
        {number}
      </span>
      <div className="min-w-0">
        <h2 id={`section-${number}`} className="text-xl text-on-surface mb-4">
          {title}
        </h2>
        {children}
      </div>
    </section>
  );
}

function YearField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-semibold text-on-surface mb-2">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type="number"
          min="1900"
          max="2100"
          inputMode="numeric"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="field pr-10 tabular-nums"
        />
        <Icon name="calendar" size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-subtle pointer-events-none" />
      </div>
    </div>
  );
}
