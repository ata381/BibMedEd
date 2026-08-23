"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { searchApi, adaptersApi, AdapterInfo } from "@/lib/api";
import toast from "react-hot-toast";

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
  const [rawQuery, setRawQuery] = useState("");
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [source, setSource] = useState("pubmed");

  // PubMed uses field tags like [PDAT]; OpenAlex and others use plain text search
  const pubmedQuery = `(${topicA}) ${operator} (${topicB}) AND ("${yearStart}/01/01"[PDAT] : "${yearEnd}/12/31"[PDAT])`;
  const genericQuery = `(${topicA}) ${operator} (${topicB})`;
  const builtQuery = source === "pubmed" ? pubmedQuery : genericQuery;
  const queryString = advancedMode ? rawQuery : builtQuery;

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const redirectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  // Cleanup polling + pending redirect on unmount AND whenever the viewed
  // project changes. The App Router does not remount this page when only the
  // `[id]` segment changes, so a search started on a previous project would
  // otherwise keep polling/redirecting in the background after the user
  // navigates to a different project's search page.
  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
      if (pollRef.current) clearInterval(pollRef.current);
      if (redirectTimeoutRef.current) clearTimeout(redirectTimeoutRef.current);
    };
  }, [projectId]);

  useEffect(() => {
    adaptersApi.list().then(res => setAdapters(res.data)).catch(() => {});
  }, []);

  const handleSearch = useCallback(async () => {
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
            setProgress({ found, fetched: 0, total: Math.min(found, 2000) });
          } else if (found > 0 && fetched > 0) {
            const total = Math.min(found, 2000);
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
            }, 500);
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
      }, 2000);
    } catch {
      if (cancelledRef.current) return;
      setStatus("Failed to start search.");
      setLoading(false);
      toast.error("Could not start search. Is the backend running?");
    }
  }, [projectId, queryString, source, yearStart, yearEnd, router]);

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      {/* Hero */}
      <section className="mb-16">
        <h1 className="text-5xl font-extrabold text-primary tracking-tight mb-4" style={{fontFamily:"var(--font-display)"}}>Precision Search Strategy</h1>
        <p className="text-on-surface-muted text-lg max-w-2xl leading-relaxed">Construct high-fidelity queries using MeSH term mapping and bibliometric operators.</p>
      </section>

      {/* Mode Toggle */}
      <div role="group" aria-label="Query mode" className="flex items-center gap-4 mb-8">
        <button onClick={() => {
          if (advancedMode && rawQuery && rawQuery !== builtQuery) {
            if (!confirm("Switching to Query Builder will discard your raw query edits. Continue?")) return;
          }
          setAdvancedMode(false);
        }}
          aria-pressed={!advancedMode}
          className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${!advancedMode ? "bg-primary text-on-primary" : "bg-surface-sunken text-on-surface-muted hover:bg-surface-hover"}`}>
          <span aria-hidden="true" className="material-symbols-outlined text-sm mr-1 align-middle">tune</span>
          Query Builder
        </button>
        <button onClick={() => { if (!advancedMode) { setAdvancedMode(true); setRawQuery(builtQuery); } }}
          aria-pressed={advancedMode}
          className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${advancedMode ? "bg-primary text-on-primary" : "bg-surface-sunken text-on-surface-muted hover:bg-surface-hover"}`}>
          <span aria-hidden="true" className="material-symbols-outlined text-sm mr-1 align-middle">terminal</span>
          Advanced Query (Raw)
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Parameters */}
        <div className="lg:col-span-8 space-y-8">
          {advancedMode ? (
            /* Raw Query Editor */
            <div className="bg-surface-raised rounded-xl p-8 shadow-sm">
              <h2 className="font-bold text-xl text-primary mb-2" style={{fontFamily:"var(--font-display)"}}>Raw Query</h2>
              <p className="text-sm text-on-surface-muted mb-6">{source === "pubmed" ? "Paste or write your full PubMed/MEDLINE query with MeSH terms, field tags, and Boolean operators." : `Enter your search query for ${adapters.find(a => a.name === source)?.display_name || source}. Use plain text keywords and Boolean operators.`}</p>
              <label htmlFor="raw-query" className="sr-only">Raw query</label>
              <textarea
                id="raw-query"
                value={rawQuery}
                onChange={e => setRawQuery(e.target.value)}
                rows={8}
                placeholder={'(Education, Medical[Mesh] OR "medical education"[tiab]) AND (Artificial Intelligence[Mesh] OR AI[tiab]) AND ("2020"[Date - Publication] : "3000"[Date - Publication])'}
                className="w-full bg-code-bg text-code-fg font-mono text-sm rounded-lg px-5 py-4 border border-divider focus:border-primary outline-none resize-none leading-relaxed placeholder-[#3e5578]"
              />
              <div className="mt-4 flex gap-3 flex-wrap">
                <span className="text-[10px] font-bold text-on-surface-muted uppercase tracking-widest py-1">Common tags:</span>
                {["[Mesh]", "[tiab]", "[PDAT]", "[AU]", "[TA]"].map(tag => (
                  <button type="button" key={tag} onClick={() => setRawQuery(q => q + tag)}
                    className="min-h-6 px-2 py-1 bg-primary-container text-on-primary-container rounded text-[10px] font-bold hover:bg-primary-container transition-colors">
                    {tag}
                  </button>
                ))}
                <div className="flex-1" />
                <button type="button" onClick={() => setRawQuery("")}
                  className="min-h-6 px-3 py-1 bg-danger-container text-danger rounded text-[10px] font-bold hover:bg-danger-container transition-colors">
                  Clear Text
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Topics */}
              <div className="bg-surface-raised rounded-xl p-8 shadow-sm">
                <h2 className="font-bold text-xl text-primary mb-6" style={{fontFamily:"var(--font-display)"}}>1. Define Research Topics</h2>
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <label htmlFor="topic-a" className="w-20 bg-primary-hover text-on-primary px-3 py-1.5 rounded-lg text-center font-bold text-xs">TOPIC A</label>
                    <input id="topic-a" value={topicA} onChange={e => setTopicA(e.target.value)}
                      className="flex-1 bg-surface-sunken rounded-lg px-4 py-3 text-sm font-medium border-b-2 border-transparent focus:border-primary focus:bg-surface-sunken transition-all outline-none" />
                  </div>
                  <div className="pl-24 flex items-center gap-6">
                    <div className="h-6 w-[1px] bg-outline/30" />
                    <div role="radiogroup" aria-label="Boolean operator" className="flex gap-2">
                      {["AND", "OR", "NOT"].map(op => (
                        <label key={op} className="cursor-pointer">
                          <input
                            type="radio"
                            name="boolean-operator"
                            value={op}
                            checked={operator === op}
                            onChange={() => setOperator(op)}
                            className="peer sr-only"
                          />
                          <span className={`inline-flex items-center min-h-6 px-3 py-1 text-[10px] font-bold rounded uppercase peer-focus-visible:outline-2 peer-focus-visible:outline-[color:var(--color-focus-ring)] peer-focus-visible:outline-offset-2 ${operator === op ? "bg-primary text-on-primary" : "bg-surface-hover text-on-surface-muted hover:bg-surface-hover"}`}>
                            {op}
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <label htmlFor="topic-b" className="w-20 bg-primary-container text-on-primary-container px-3 py-1.5 rounded-lg text-center font-bold text-xs">TOPIC B</label>
                    <input id="topic-b" value={topicB} onChange={e => setTopicB(e.target.value)}
                      className="flex-1 bg-surface-sunken rounded-lg px-4 py-3 text-sm font-medium border-b-2 border-transparent focus:border-primary focus:bg-surface-sunken transition-all outline-none" />
                  </div>
                </div>
              </div>

              {/* Date Range */}
              <div className="bg-surface-raised rounded-xl p-8 shadow-sm">
                <h2 className="font-bold text-xl text-primary mb-6" style={{fontFamily:"var(--font-display)"}}>2. Publication Date Range</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
                  <div>
                    <label htmlFor="year-start" className="text-[10px] font-bold text-on-surface-muted uppercase tracking-widest block mb-2">Start Year</label>
                    <div className="bg-surface-sunken rounded-lg px-4 py-3 flex items-center justify-between">
                      <input id="year-start" type="number" min="1900" max="2100" inputMode="numeric" value={yearStart} onChange={e => setYearStart(e.target.value)} className="min-h-6 bg-transparent border-none text-sm font-medium outline-none w-full" />
                      <span aria-hidden="true" className="material-symbols-outlined text-on-surface-subtle">calendar_today</span>
                    </div>
                  </div>
                  <div>
                    <label htmlFor="year-end" className="text-[10px] font-bold text-on-surface-muted uppercase tracking-widest block mb-2">End Year</label>
                    <div className="bg-surface-sunken rounded-lg px-4 py-3 flex items-center justify-between">
                      <input id="year-end" type="number" min="1900" max="2100" inputMode="numeric" value={yearEnd} onChange={e => setYearEnd(e.target.value)} className="min-h-6 bg-transparent border-none text-sm font-medium outline-none w-full" />
                      <span aria-hidden="true" className="material-symbols-outlined text-on-surface-subtle">calendar_today</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Data Source */}
              {adapters.length > 1 && (
                <div className="bg-surface-raised rounded-xl p-8 shadow-sm">
                  <h2 className="font-bold text-xl text-primary mb-6" style={{fontFamily:"var(--font-display)"}}>3. Data Source</h2>
                  <div role="radiogroup" aria-label="Data source" className="flex gap-3 flex-wrap">
                    {adapters.map(a => (
                      <label key={a.name} className="cursor-pointer">
                        <input
                          type="radio"
                          name="data-source"
                          value={a.name}
                          checked={source === a.name}
                          onChange={() => setSource(a.name)}
                          className="peer sr-only"
                        />
                        <span className={`inline-flex items-center min-h-9 px-4 py-2 rounded-lg text-sm font-bold transition-all peer-focus-visible:outline-2 peer-focus-visible:outline-[color:var(--color-focus-ring)] peer-focus-visible:outline-offset-2 ${source === a.name ? "bg-primary text-on-primary" : "bg-surface-sunken text-on-surface-muted hover:bg-surface-hover"}`}>
                          {a.display_name}
                          {a.requires_api_key && <span className="ml-1 text-[10px]">(API key)</span>}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Right: Query Preview */}
        <div className="lg:col-span-4">
          <div className="bg-primary text-on-primary rounded-xl p-8 sticky top-24 shadow-lg">
            <div className="flex items-center gap-2 mb-6">
              <span aria-hidden="true" className="material-symbols-outlined" style={{fontVariationSettings:"'FILL' 1"}}>terminal</span>
              <h2 className="font-bold text-lg" style={{fontFamily:"var(--font-display)"}}>Query Preview</h2>
            </div>
            <div className="bg-code-bg rounded-lg p-5 font-mono text-xs leading-relaxed text-code-fg mb-6 border border-white/20 whitespace-pre-wrap break-all">
              {advancedMode ? (rawQuery || <span className="text-code-fg/80 italic">Enter your raw query...</span>) : source === "pubmed" ? (
                <>({topicA}) <span className="text-accent">{operator}</span> ({topicB}) <span className="text-accent">AND</span> (&quot;{yearStart}/01/01&quot;[PDAT] : &quot;{yearEnd}/12/31&quot;[PDAT])</>
              ) : (
                <>({topicA}) <span className="text-accent">{operator}</span> ({topicB})<br/><span className="text-code-fg/80 text-[10px]">+ date filter: {yearStart}–{yearEnd}</span></>
              )}
            </div>
            {status && (
              <div className="mb-4" role="status" aria-live="polite" aria-atomic="true">
                <div className="text-xs text-accent mb-2">{loading && <span aria-hidden="true" className="material-symbols-outlined animate-spin text-sm mr-1 inline-block">sync</span>}{status}</div>
                {progress && progress.total > 0 && (
                  <div role="progressbar" aria-label="Search records fetched" aria-valuemin={0} aria-valuemax={progress.total} aria-valuenow={progress.fetched} className="w-full bg-primary-hover rounded-full h-2 overflow-hidden">
                    <div className="bg-secondary-container h-2 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.round((progress.fetched / progress.total) * 100))}%` }} />
                  </div>
                )}
              </div>
            )}
            <button onClick={handleSearch} disabled={loading}
              className="w-full bg-secondary-container text-on-secondary-container font-extrabold py-4 rounded-lg hover:bg-accent transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              style={{fontFamily:"var(--font-display)"}}>
              {loading ? "Searching..." : "Execute Search"}
              {!loading && <span aria-hidden="true" className="material-symbols-outlined">arrow_forward</span>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
