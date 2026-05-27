"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  publicationsApi,
  searchApi,
  Publication,
  SearchStatus,
  ExclusionReason,
  EXCLUSION_REASON_LABELS,
} from "@/lib/api";
import toast from "react-hot-toast";

function ExcludeButton({
  pub,
  projectId,
  onToggle,
}: {
  pub: Publication;
  projectId: number;
  onToggle: (id: number, excluded: boolean, reason: ExclusionReason | null) => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);

  // Close on outside click. Use `click` (not `mousedown`) so the trigger's own
  // click handler can close-then-reopen-then-close without racing.
  useEffect(() => {
    if (!showMenu) return;
    const onDocClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setShowMenu(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("click", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [showMenu]);

  // Move focus into the menu when it opens so keyboard users can reach the items.
  useEffect(() => {
    if (showMenu) firstItemRef.current?.focus();
  }, [showMenu]);

  const doToggle = async (reason?: ExclusionReason) => {
    setShowMenu(false);
    try {
      const res = await publicationsApi.toggleExclude(projectId, pub.id, reason);
      onToggle(pub.id, res.data.excluded, res.data.exclusion_reason);
      if (res.data.excluded) {
        const label = res.data.exclusion_reason ? EXCLUSION_REASON_LABELS[res.data.exclusion_reason] : "Excluded";
        toast.success(`Excluded: ${label}`);
      } else {
        toast.success("Publication included");
      }
    } catch {
      toast.error("Failed to update publication.");
    }
  };

  const handlePrimary = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (pub.excluded) {
      doToggle();  // re-include
    } else {
      setShowMenu((v) => !v);
    }
  };

  // Truncate the title for the accessible label so a screen reader announcing 20
  // identical "Included" buttons gets enough context to disambiguate.
  const labelTitle = (pub.title || "Untitled").slice(0, 60);
  const triggerLabel = pub.excluded
    ? `Re-include "${labelTitle}"`
    : `Exclude "${labelTitle}" — open PRISMA reason picker`;

  return (
    <div className="relative" ref={containerRef}>
      <button
        ref={triggerRef}
        onClick={handlePrimary}
        aria-label={triggerLabel}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
          pub.excluded
            ? "bg-red-50 text-red-600 hover:bg-red-100"
            : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
        }`}
        aria-haspopup={!pub.excluded ? "menu" : undefined}
        aria-expanded={!pub.excluded ? showMenu : undefined}
      >
        <span aria-hidden="true" className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
          {pub.excluded ? "close" : "check_circle"}
        </span>
        {pub.excluded ? "Excluded" : "Included"}
      </button>
      {pub.excluded && pub.exclusion_reason && (
        <span className="block mt-1 text-[9px] text-red-600/80 text-center max-w-[150px] truncate" title={EXCLUSION_REASON_LABELS[pub.exclusion_reason]}>
          {EXCLUSION_REASON_LABELS[pub.exclusion_reason]}
        </span>
      )}
      {showMenu && !pub.excluded && (
        <div
          role="menu"
          aria-label="Select exclusion reason"
          className="absolute right-0 mt-1 w-64 bg-surface-raised rounded-lg shadow-lg border border-divider z-10 py-1 text-xs"
        >
          <p className="px-3 pt-2 pb-1 text-[9px] font-bold uppercase tracking-widest text-on-surface-muted">
            Exclude — PRISMA reason
          </p>
          {(Object.keys(EXCLUSION_REASON_LABELS) as ExclusionReason[]).map((code, idx) => (
            <button
              key={code}
              ref={idx === 0 ? firstItemRef : undefined}
              role="menuitem"
              onClick={(e) => {
                e.stopPropagation();
                doToggle(code);
              }}
              className="block w-full text-left px-3 py-1.5 hover:bg-surface-hover focus:bg-surface-hover focus:outline-none text-on-surface"
            >
              {EXCLUSION_REASON_LABELS[code]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ResultsReview() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);
  const [publications, setPublications] = useState<Publication[]>([]);
  const [total, setTotal] = useState(0);
  const [excludedCount, setExcludedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchStats, setSearchStats] = useState<SearchStatus | null>(null);
  const limit = 20;

  const includedCount = total - excludedCount;

  const handleToggleExclude = (pubId: number, excluded: boolean, reason: ExclusionReason | null) => {
    setPublications(prev => prev.map(p => p.id === pubId ? { ...p, excluded, exclusion_reason: reason } : p));
    setExcludedCount(prev => excluded ? prev + 1 : prev - 1);
  };

  useEffect(() => {
    searchApi.latest(projectId).then(res => setSearchStats(res.data)).catch(() => {});
  }, [projectId]);

  const [refreshTick, setRefreshTick] = useState(0);
  const refresh = () => setRefreshTick(t => t + 1);

  useEffect(() => {
    // One-shot setLoading flag at the start of a fetch is the canonical
    // pattern until we migrate to a fetch library (React Query / SWR /
    // Next 16 `use(promise)`). The compiler's cascading-renders concern
    // doesn't apply here because the effect runs once per dep change.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    // Use an abort controller so a fast pagination click doesn't race the previous
    // request and clobber excludedCount with stale data.
    const ctrl = new AbortController();
    publicationsApi.list(projectId, { sort_by: "citation_count", order: "desc", limit, offset: (page - 1) * limit })
      .then((res) => {
        if (ctrl.signal.aborted) return;
        setPublications(res.data.items);
        setTotal(res.data.total);
        setExcludedCount(res.data.excluded_count ?? 0);
      })
      .catch(() => { if (!ctrl.signal.aborted) toast.error("Failed to load publications."); })
      .finally(() => { if (!ctrl.signal.aborted) setLoading(false); });
    return () => ctrl.abort();
  }, [projectId, page, refreshTick]);

  const totalPages = Math.max(1, Math.ceil(total / limit));

  const pageWindow = (() => {
    const windowSize = 5;
    if (totalPages <= windowSize) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    const half = Math.floor(windowSize / 2);
    let start = Math.max(1, page - half);
    const end = Math.min(totalPages, start + windowSize - 1);
    start = Math.max(1, end - windowSize + 1);
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  })();

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      {/* Editorial Header */}
      <section className="mb-12 border-l-4 border-primary pl-8">
        <h1 className="text-4xl font-extrabold text-primary tracking-tight mb-2" style={{fontFamily:"var(--font-display)"}}>
          Results Review
        </h1>
        <div className="flex items-center gap-4">
          <p className="text-on-surface-muted font-medium">{total} unique publications found</p>
          <span className="w-1.5 h-1.5 bg-accent rounded-full" />
          <p className="text-on-surface-muted opacity-70">Duplicates removed</p>
        </div>
      </section>

      {/* Cap notice — compares the upstream record count against what BibMedEd processed.
          `result_count` is records persisted to the DB; `duplicate_count` is records removed
          by cross-source deduplication (so the sum is "records the pipeline saw"). NOT the
          publications-list `total`, which would shift if the list endpoint were ever filtered.
          For fresh projects this is exact; for re-runs over a corpus with pre-existing rows
          some records may have been skipped as duplicates of in-DB pubs without being counted
          here — the cap-notice may therefore under-trigger on re-runs but never over-trigger. */}
      {(() => {
        const raw = searchStats?.raw_result_count ?? 0;
        const fetched = (searchStats?.result_count ?? 0) + (searchStats?.duplicate_count ?? 0);
        if (raw <= 0 || fetched <= 0 || raw <= fetched) return null;
        return (
        <div className="mb-6 rounded-xl border-l-4 border-warning bg-warning-container/40 px-5 py-4">
          <div className="flex items-start gap-3" role="status">
            <span aria-hidden="true" className="material-symbols-outlined text-warning mt-0.5" style={{fontVariationSettings:"'FILL' 1"}}>warning</span>
            <div>
              <p className="text-sm font-bold text-on-surface">
                Search returned {raw.toLocaleString()} records — only the first {fetched.toLocaleString()} were fetched.
              </p>
              <p className="text-xs text-on-surface-muted mt-1">
                The remainder were not retrieved. For PRISMA / journal submissions, rerun the search with a higher <code className="font-mono">max_results</code> or narrow the query — silently truncating a systematic review&apos;s record set is not journal-acceptable.
              </p>
            </div>
          </div>
        </div>
        );
      })()}

      {/* PRISMA Flow */}
      <section
        aria-label={`PRISMA flow: ${(searchStats?.raw_result_count ?? 0).toLocaleString()} identified, ${searchStats?.duplicate_count ?? 0} duplicates removed, ${excludedCount} manually excluded, ${includedCount.toLocaleString()} included`}
        className="bg-surface-raised rounded-xl p-8 shadow-sm mb-10">
        <div className="flex items-center gap-3 mb-6">
          <span aria-hidden="true" className="material-symbols-outlined text-primary">account_tree</span>
          <h3 className="font-bold text-xl text-primary" style={{fontFamily:"var(--font-display)"}}>PRISMA Flow</h3>
          <span className="text-[10px] font-bold py-1 px-2 bg-primary-container text-primary rounded-full uppercase tracking-widest">Identification</span>
        </div>
        <div className="flex items-center gap-4 overflow-x-auto pb-1 -mx-2 px-2 [&>div]:flex-shrink-0 [&>div.flex-1]:min-w-[140px]">
          {/* Raw Results */}
          <div className="flex-1 bg-surface-sunken rounded-xl p-5 text-center">
            <p className="text-[10px] font-bold text-on-surface-muted uppercase tracking-widest mb-2">Records Identified</p>
            <p className="text-3xl font-extrabold text-primary" style={{fontFamily:"var(--font-display)"}}>
              {searchStats?.raw_result_count?.toLocaleString() ?? "—"}
            </p>
            <p className="text-[10px] text-on-surface-muted mt-1">via database search</p>
          </div>
          <span aria-hidden="true" className="material-symbols-outlined text-on-surface-subtle text-2xl">arrow_forward</span>
          {/* Duplicates Removed */}
          <div className="flex-1 bg-danger-container rounded-xl p-5 text-center group relative">
            <p className="text-[10px] font-bold text-on-surface-muted uppercase tracking-widest mb-2">Duplicates Removed</p>
            <p className="text-3xl font-extrabold text-danger" style={{fontFamily:"var(--font-display)"}}>
              {searchStats?.duplicate_count != null ? `-${searchStats.duplicate_count}` : "—"}
            </p>
            <p className="text-[10px] text-on-surface-muted mt-1">cross-journal overlaps</p>
            <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 bg-code-bg text-code-fg text-[10px] py-1.5 px-3 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 pointer-events-none">
              Matched via exact PMID and DOI cross-check
            </div>
          </div>
          <span aria-hidden="true" className="material-symbols-outlined text-on-surface-subtle text-2xl">arrow_forward</span>
          {/* Manually Excluded */}
          {excludedCount > 0 && (
            <>
              <div className="flex-1 bg-warning-container rounded-xl p-5 text-center">
                <p className="text-[10px] font-bold text-on-surface-muted uppercase tracking-widest mb-2">Manually Excluded</p>
                <p className="text-3xl font-extrabold text-warning" style={{fontFamily:"var(--font-display)"}}>
                  -{excludedCount}
                </p>
                <p className="text-[10px] text-on-surface-muted mt-1">by reviewer</p>
              </div>
              <span aria-hidden="true" className="material-symbols-outlined text-on-surface-subtle text-2xl">arrow_forward</span>
            </>
          )}
          {/* Included */}
          <div className="flex-1 bg-primary rounded-xl p-5 text-center text-white">
            <p className="text-[10px] font-bold uppercase tracking-widest mb-2 opacity-80">Records Included</p>
            <p className="text-3xl font-extrabold" style={{fontFamily:"var(--font-display)"}}>
              {includedCount.toLocaleString()}
            </p>
            <p className="text-[10px] mt-1 opacity-70">for analysis</p>
          </div>
        </div>
      </section>

      {/* Action Bar */}
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <button onClick={async () => {
            if (!confirm("Exclude all publications with 0 citations? This helps focus analysis on impactful papers.")) return;
            try {
              const res = await publicationsApi.bulkExclude(projectId, 0);
              toast.success(`${res.data.excluded_count} publications excluded.`);
              // Refetch from server — the optimistic client predicate could diverge from
              // the server's SQL predicate (especially around NULL citation counts).
              refresh();
            } catch { toast.error("Bulk exclude failed."); }
          }}
            disabled={total === 0 && !loading}
            className="flex items-center gap-2 px-4 py-2 bg-warning-container text-warning rounded-lg font-bold text-xs hover:bg-warning-container transition disabled:opacity-40 disabled:cursor-not-allowed">
            <span aria-hidden="true" className="material-symbols-outlined text-sm">filter_alt</span>
            Exclude 0-citation papers
          </button>
        </div>
        <button onClick={() => includedCount > 0 ? router.push(`/projects/${projectId}/dashboard`) : toast.error("No publications to analyze. Run a search first.")}
          disabled={includedCount === 0 && !loading}
          className="flex items-center gap-2 px-6 py-2.5 bg-primary text-white rounded-lg font-bold text-sm hover:opacity-90 transition disabled:opacity-40 disabled:cursor-not-allowed">
          <span aria-hidden="true" className="material-symbols-outlined text-sm">auto_awesome</span>
          Run Bibliometric Analysis
        </button>
      </div>

      {/* Publication Cards */}
      <div style={{ minHeight: "600px" }}>
      {loading ? (
        <div className="text-on-surface-muted text-center py-20">Loading publications...</div>
      ) : publications.length === 0 ? (
        <div className="text-center py-20">
          <span className="material-symbols-outlined text-6xl text-on-surface-subtle mb-4 block">search_off</span>
          <h3 className="text-xl font-bold text-on-surface mb-2" style={{fontFamily:"var(--font-display)"}}>No Publications Found</h3>
          <p className="text-sm text-on-surface-muted mb-6">Run a search first to populate results for this project.</p>
          <button onClick={() => router.push(`/projects/${projectId}/search`)}
            className="px-6 py-2.5 bg-primary text-white rounded-lg font-bold text-sm hover:opacity-90 transition">
            Go to Search
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {publications.map((pub) => (
            <article key={pub.id} className={`group bg-surface-raised p-8 rounded-xl transition-all duration-300 hover:shadow-[0px_12px_32px_rgba(25,28,30,0.08)] border border-transparent hover:border-divider ${pub.excluded ? "opacity-50" : ""}`}>
              <div className="flex items-start justify-between gap-6">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-[10px] font-bold py-1 px-2 bg-surface-hover rounded text-on-surface-muted uppercase tracking-wider">
                      {pub.publication_type || "Article"}
                    </span>
                    {(pub.citation_count ?? 0) > 50 && (
                      <span className="text-[10px] font-bold py-1 px-2 bg-primary-container text-primary rounded uppercase tracking-wider">High Impact</span>
                    )}
                  </div>
                  <h3 className={`text-xl font-bold mb-3 leading-tight transition-colors ${pub.excluded ? "text-on-surface-muted line-through" : "text-primary group-hover:text-primary"}`} style={{fontFamily:"var(--font-display)"}}>
                    {pub.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-y-2 text-sm text-on-surface-muted font-medium">
                    <span className="text-on-surface font-bold">
                      {pub.authors.slice(0, 2).map(a => a.name).join(", ")}{pub.authors.length > 2 ? " et al." : ""}
                    </span>
                    <span className="mx-2 text-on-surface-subtle">•</span>
                    <span>{pub.journal_name || "Unknown"}</span>
                    <span className="mx-2 text-on-surface-subtle">•</span>
                    <span>{pub.year}</span>
                  </div>
                </div>
                <div className="flex flex-col items-center gap-3 shrink-0">
                  <div className="flex flex-col items-center justify-center min-w-[64px] h-16 bg-surface-sunken rounded-lg">
                    <span className="text-lg font-extrabold text-primary">{pub.citation_count ?? 0}</span>
                    <span className="text-[8px] font-bold uppercase tracking-tighter opacity-60">Citations</span>
                  </div>
                  <ExcludeButton pub={pub} projectId={projectId} onToggle={handleToggleExclude} />
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-12 flex justify-center">
          <nav aria-label="Pagination" className="flex items-center gap-1 bg-surface-sunken rounded-full px-2 py-1">
            <button onClick={() => setPage(Math.max(1, page - 1))} aria-label="Previous page" disabled={page === 1} className="p-2 hover:bg-surface-hover rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
              <span aria-hidden="true" className="material-symbols-outlined text-sm">chevron_left</span>
            </button>
            {pageWindow[0] > 1 && (
              <>
                <button onClick={() => setPage(1)} aria-label="Page 1" className="px-4 py-1.5 hover:bg-surface-hover rounded-full text-xs font-bold">1</button>
                {pageWindow[0] > 2 && <span aria-hidden="true" className="px-2 text-on-surface-subtle text-xs">...</span>}
              </>
            )}
            {pageWindow.map((p) => (
              <button key={p} onClick={() => setPage(p)}
                aria-label={`Page ${p}`}
                aria-current={page === p ? "page" : undefined}
                className={`px-4 py-1.5 rounded-full text-xs font-bold ${page === p ? "bg-primary text-white" : "hover:bg-surface-hover"}`}>
                {p}
              </button>
            ))}
            {pageWindow[pageWindow.length - 1] < totalPages && (
              <>
                {pageWindow[pageWindow.length - 1] < totalPages - 1 && <span aria-hidden="true" className="px-2 text-on-surface-subtle text-xs">...</span>}
                <button onClick={() => setPage(totalPages)} aria-label={`Page ${totalPages}`} className="px-4 py-1.5 hover:bg-surface-hover rounded-full text-xs font-bold">{totalPages}</button>
              </>
            )}
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} aria-label="Next page" disabled={page === totalPages} className="p-2 hover:bg-surface-hover rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
              <span aria-hidden="true" className="material-symbols-outlined text-sm">chevron_right</span>
            </button>
          </nav>
        </div>
      )}
    </div>
  );
}
