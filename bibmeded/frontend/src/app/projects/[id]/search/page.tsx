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

  // Cleanup polling on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    adaptersApi.list().then(res => setAdapters(res.data)).catch(() => {});
  }, []);

  const handleSearch = useCallback(async () => {
    setLoading(true);
    setStatus("Submitting search...");
    try {
      const res = await searchApi.trigger(projectId, queryString, source, yearStart, yearEnd);
      const queryId = res.data.query_id;
      setStatus("Search dispatched...");
      setProgress(null);
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const s = await searchApi.status(projectId, queryId);
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
            setTimeout(() => router.push(`/projects/${projectId}/results`), 500);
          } else if (s.data.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setStatus("Search failed.");
            setProgress(null);
            setLoading(false);
            toast.error("Search failed. Please try again.");
          }
        } catch {
          if (pollRef.current) clearInterval(pollRef.current);
          setStatus("Error polling status.");
          setProgress(null);
          setLoading(false);
          toast.error("Lost connection while checking search status.");
        }
      }, 2000);
    } catch {
      setStatus("Failed to start search.");
      setLoading(false);
      toast.error("Could not start search. Is the backend running?");
    }
  }, [projectId, queryString, source, router]);

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      {/* Hero */}
      <section className="mb-16">
        <h1 className="text-5xl font-extrabold text-[#001e4f] tracking-tight mb-4" style={{fontFamily:"'Manrope',sans-serif"}}>Precision Search Strategy</h1>
        <p className="text-[#515f74] text-lg max-w-2xl leading-relaxed">Construct high-fidelity queries using MeSH term mapping and bibliometric operators.</p>
      </section>

      {/* Mode Toggle */}
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => {
          if (advancedMode && rawQuery && rawQuery !== builtQuery) {
            if (!confirm("Switching to Query Builder will discard your raw query edits. Continue?")) return;
          }
          setAdvancedMode(false);
        }}
          className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${!advancedMode ? "bg-[#001e4f] text-white" : "bg-[#eceef0] text-[#43474e] hover:bg-[#e6e8ea]"}`}>
          <span className="material-symbols-outlined text-sm mr-1 align-middle">tune</span>
          Query Builder
        </button>
        <button onClick={() => { if (!advancedMode) { setAdvancedMode(true); setRawQuery(builtQuery); } }}
          className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${advancedMode ? "bg-[#001e4f] text-white" : "bg-[#eceef0] text-[#43474e] hover:bg-[#e6e8ea]"}`}>
          <span className="material-symbols-outlined text-sm mr-1 align-middle">terminal</span>
          Advanced Query (Raw)
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Parameters */}
        <div className="lg:col-span-8 space-y-8">
          {advancedMode ? (
            /* Raw Query Editor */
            <div className="bg-white rounded-xl p-8 shadow-sm">
              <h2 className="font-bold text-xl text-[#001e4f] mb-2" style={{fontFamily:"'Manrope',sans-serif"}}>Raw Query</h2>
              <p className="text-sm text-[#43474e] mb-6">{source === "pubmed" ? "Paste or write your full PubMed/MEDLINE query with MeSH terms, field tags, and Boolean operators." : `Enter your search query for ${adapters.find(a => a.name === source)?.display_name || source}. Use plain text keywords and Boolean operators.`}</p>
              <textarea
                value={rawQuery}
                onChange={e => setRawQuery(e.target.value)}
                rows={8}
                placeholder={'(Education, Medical[Mesh] OR "medical education"[tiab]) AND (Artificial Intelligence[Mesh] OR AI[tiab]) AND ("2020"[Date - Publication] : "3000"[Date - Publication])'}
                className="w-full bg-[#0a1628] text-[#93f2f2] font-mono text-sm rounded-lg px-5 py-4 border border-[#1e293b] focus:border-[#2b5bb5] outline-none resize-none leading-relaxed placeholder-[#3e5578]"
              />
              <div className="mt-4 flex gap-3 flex-wrap">
                <span className="text-[10px] font-bold text-[#43474e] uppercase tracking-widest py-1">Common tags:</span>
                {["[Mesh]", "[tiab]", "[PDAT]", "[AU]", "[TA]"].map(tag => (
                  <button key={tag} onClick={() => setRawQuery(q => q + tag)}
                    className="px-2 py-1 bg-[#d5e3fc] text-[#001945] rounded text-[10px] font-bold hover:bg-[#bdd0f7] transition-colors">
                    {tag}
                  </button>
                ))}
                <div className="flex-1" />
                <button onClick={() => setRawQuery("")}
                  className="px-3 py-1 bg-red-100 text-red-700 rounded text-[10px] font-bold hover:bg-red-200 transition-colors">
                  Clear Text
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Topics */}
              <div className="bg-white rounded-xl p-8 shadow-sm">
                <h2 className="font-bold text-xl text-[#001e4f] mb-6" style={{fontFamily:"'Manrope',sans-serif"}}>1. Define Research Topics</h2>
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="w-20 bg-[#00327a] text-white px-3 py-1.5 rounded-lg text-center font-bold text-xs">TOPIC A</div>
                    <input value={topicA} onChange={e => setTopicA(e.target.value)}
                      className="flex-1 bg-[#eceef0] rounded-lg px-4 py-3 text-sm font-medium border-b-2 border-transparent focus:border-[#2b5bb5] focus:bg-[#f2f4f6] transition-all outline-none" />
                  </div>
                  <div className="pl-24 flex items-center gap-6">
                    <div className="h-6 w-[1px] bg-[#c4c6cf]/30" />
                    <div className="flex gap-2">
                      {["AND", "OR", "NOT"].map(op => (
                        <button key={op} onClick={() => setOperator(op)}
                          className={`px-3 py-1 text-[10px] font-bold rounded uppercase ${operator === op ? "bg-[#001e4f] text-white" : "bg-[#e6e8ea] text-[#43474e] hover:bg-[#e0e3e5]"}`}>
                          {op}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="w-20 bg-[#d5e3fc] text-[#57657a] px-3 py-1.5 rounded-lg text-center font-bold text-xs">TOPIC B</div>
                    <input value={topicB} onChange={e => setTopicB(e.target.value)}
                      className="flex-1 bg-[#eceef0] rounded-lg px-4 py-3 text-sm font-medium border-b-2 border-transparent focus:border-[#2b5bb5] focus:bg-[#f2f4f6] transition-all outline-none" />
                  </div>
                </div>
              </div>

              {/* Date Range */}
              <div className="bg-white rounded-xl p-8 shadow-sm">
                <h2 className="font-bold text-xl text-[#001e4f] mb-6" style={{fontFamily:"'Manrope',sans-serif"}}>2. Publication Date Range</h2>
                <div className="grid grid-cols-2 gap-8">
                  <div>
                    <label className="text-[10px] font-bold text-[#43474e] uppercase tracking-widest block mb-2">Start Year</label>
                    <div className="bg-[#eceef0] rounded-lg px-4 py-3 flex items-center justify-between">
                      <input type="text" value={yearStart} onChange={e => setYearStart(e.target.value)} className="bg-transparent border-none text-sm font-medium outline-none w-full" />
                      <span className="material-symbols-outlined text-[#c4c6cf]">calendar_today</span>
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] font-bold text-[#43474e] uppercase tracking-widest block mb-2">End Year</label>
                    <div className="bg-[#eceef0] rounded-lg px-4 py-3 flex items-center justify-between">
                      <input type="text" value={yearEnd} onChange={e => setYearEnd(e.target.value)} className="bg-transparent border-none text-sm font-medium outline-none w-full" />
                      <span className="material-symbols-outlined text-[#c4c6cf]">calendar_today</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Data Source */}
              {adapters.length > 1 && (
                <div className="bg-white rounded-xl p-8 shadow-sm">
                  <h2 className="font-bold text-xl text-[#001e4f] mb-6" style={{fontFamily:"'Manrope',sans-serif"}}>3. Data Source</h2>
                  <div className="flex gap-3 flex-wrap">
                    {adapters.map(a => (
                      <button key={a.name} onClick={() => setSource(a.name)}
                        className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${source === a.name ? "bg-[#001e4f] text-white" : "bg-[#eceef0] text-[#43474e] hover:bg-[#e6e8ea]"}`}>
                        {a.display_name}
                        {a.requires_api_key && <span className="ml-1 text-[10px] opacity-60">(API key)</span>}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Right: Query Preview */}
        <div className="lg:col-span-4">
          <div className="bg-[#001e4f] text-white rounded-xl p-8 sticky top-24 shadow-lg">
            <div className="flex items-center gap-2 mb-6">
              <span className="material-symbols-outlined" style={{fontVariationSettings:"'FILL' 1"}}>terminal</span>
              <h2 className="font-bold text-lg" style={{fontFamily:"'Manrope',sans-serif"}}>3. Query Preview</h2>
            </div>
            <div className="bg-[#00327a]/50 rounded-lg p-5 font-mono text-xs leading-relaxed text-[#739cfb] mb-6 border border-white/10 whitespace-pre-wrap break-all">
              {advancedMode ? (rawQuery || <span className="text-[#3e5578] italic">Enter your raw query...</span>) : source === "pubmed" ? (
                <>({topicA}) <span className="text-[#93f2f2]">{operator}</span> ({topicB}) <span className="text-[#93f2f2]">AND</span> (&quot;{yearStart}/01/01&quot;[PDAT] : &quot;{yearEnd}/12/31&quot;[PDAT])</>
              ) : (
                <>({topicA}) <span className="text-[#93f2f2]">{operator}</span> ({topicB})<br/><span className="text-[#3e5578] text-[10px]">+ date filter: {yearStart}–{yearEnd}</span></>
              )}
            </div>
            {status && (
              <div className="mb-4">
                <div className="text-xs text-[#93f2f2] mb-2">{loading && <span className="material-symbols-outlined animate-spin text-sm mr-1 inline-block">sync</span>}{status}</div>
                {progress && progress.total > 0 && (
                  <div className="w-full bg-[#00327a] rounded-full h-2 overflow-hidden">
                    <div className="bg-[#93f2f2] h-2 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.round((progress.fetched / progress.total) * 100))}%` }} />
                  </div>
                )}
              </div>
            )}
            <button onClick={handleSearch} disabled={loading}
              className="w-full bg-[#93f2f2] text-[#002020] font-extrabold py-4 rounded-lg hover:bg-[#76d6d5] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              style={{fontFamily:"'Manrope',sans-serif"}}>
              {loading ? "Searching..." : "Execute Search"}
              {!loading && <span className="material-symbols-outlined">arrow_forward</span>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
