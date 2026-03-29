"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { publicationsApi, searchApi, Publication, SearchStatus } from "@/lib/api";
import toast from "react-hot-toast";

function ExcludeButton({ pub, projectId, onToggle }: { pub: Publication; projectId: number; onToggle: (id: number, excluded: boolean) => void }) {
  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await publicationsApi.toggleExclude(projectId, pub.id);
      onToggle(pub.id, res.data.excluded);
      toast.success(res.data.excluded ? "Publication excluded" : "Publication included");
    } catch {
      toast.error("Failed to update publication.");
    }
  };

  return (
    <button onClick={handleClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
        pub.excluded
          ? "bg-red-50 text-red-600 hover:bg-red-100"
          : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
      }`}>
      <span className="material-symbols-outlined text-sm" style={{fontVariationSettings:"'FILL' 1"}}>
        {pub.excluded ? "close" : "check_circle"}
      </span>
      {pub.excluded ? "Excluded" : "Included"}
    </button>
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

  const handleToggleExclude = (pubId: number, excluded: boolean) => {
    setPublications(prev => prev.map(p => p.id === pubId ? { ...p, excluded } : p));
    setExcludedCount(prev => excluded ? prev + 1 : prev - 1);
  };

  useEffect(() => {
    searchApi.latest(projectId).then(res => setSearchStats(res.data)).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    setLoading(true);
    publicationsApi.list(projectId, { sort_by: "citation_count", order: "desc", limit, offset: (page - 1) * limit })
      .then((res) => { setPublications(res.data.items); setTotal(res.data.total); setExcludedCount(res.data.excluded_count ?? 0); })
      .catch(() => toast.error("Failed to load publications."))
      .finally(() => setLoading(false));
  }, [projectId, page]);

  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      {/* Editorial Header */}
      <section className="mb-12 border-l-4 border-[#001e4f] pl-8">
        <h2 className="text-4xl font-extrabold text-[#001e4f] tracking-tight mb-2" style={{fontFamily:"'Manrope',sans-serif"}}>
          Results Review
        </h2>
        <div className="flex items-center gap-4">
          <p className="text-[#43474e] font-medium">{total} unique publications found</p>
          <span className="w-1.5 h-1.5 bg-[#76d6d5] rounded-full" />
          <p className="text-[#43474e] opacity-70">Duplicates removed</p>
        </div>
      </section>

      {/* PRISMA Flow */}
      <div className="bg-white rounded-xl p-8 shadow-sm mb-10">
        <div className="flex items-center gap-3 mb-6">
          <span className="material-symbols-outlined text-[#001e4f]">account_tree</span>
          <h3 className="font-bold text-xl text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>PRISMA Flow</h3>
          <span className="text-[10px] font-bold py-1 px-2 bg-[#d5e3fc] text-[#001945] rounded-full uppercase tracking-widest">Identification</span>
        </div>
        <div className="flex items-center gap-4">
          {/* Raw Results */}
          <div className="flex-1 bg-[#eceef0] rounded-xl p-5 text-center">
            <p className="text-[10px] font-bold text-[#43474e] uppercase tracking-widest mb-2">Records Identified</p>
            <p className="text-3xl font-extrabold text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>
              {searchStats?.raw_result_count?.toLocaleString() ?? "—"}
            </p>
            <p className="text-[10px] text-[#43474e] mt-1">via database search</p>
          </div>
          <span className="material-symbols-outlined text-[#c4c6cf] text-2xl">arrow_forward</span>
          {/* Duplicates Removed */}
          <div className="flex-1 bg-[#fff3f3] rounded-xl p-5 text-center group relative">
            <p className="text-[10px] font-bold text-[#43474e] uppercase tracking-widest mb-2">Duplicates Removed</p>
            <p className="text-3xl font-extrabold text-[#dc2626]" style={{fontFamily:"'Manrope',sans-serif"}}>
              {searchStats?.duplicate_count != null ? `-${searchStats.duplicate_count}` : "—"}
            </p>
            <p className="text-[10px] text-[#43474e] mt-1">cross-journal overlaps</p>
            <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 bg-[#191c1e] text-white text-[10px] py-1.5 px-3 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 pointer-events-none">
              Matched via exact PMID and DOI cross-check
            </div>
          </div>
          <span className="material-symbols-outlined text-[#c4c6cf] text-2xl">arrow_forward</span>
          {/* Manually Excluded */}
          {excludedCount > 0 && (
            <>
              <div className="flex-1 bg-[#fef3c7] rounded-xl p-5 text-center">
                <p className="text-[10px] font-bold text-[#43474e] uppercase tracking-widest mb-2">Manually Excluded</p>
                <p className="text-3xl font-extrabold text-[#b45309]" style={{fontFamily:"'Manrope',sans-serif"}}>
                  -{excludedCount}
                </p>
                <p className="text-[10px] text-[#43474e] mt-1">by reviewer</p>
              </div>
              <span className="material-symbols-outlined text-[#c4c6cf] text-2xl">arrow_forward</span>
            </>
          )}
          {/* Included */}
          <div className="flex-1 bg-[#001e4f] rounded-xl p-5 text-center text-white">
            <p className="text-[10px] font-bold uppercase tracking-widest mb-2 opacity-80">Records Included</p>
            <p className="text-3xl font-extrabold" style={{fontFamily:"'Manrope',sans-serif"}}>
              {includedCount.toLocaleString()}
            </p>
            <p className="text-[10px] mt-1 opacity-70">for analysis</p>
          </div>
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <button onClick={async () => {
            if (!confirm("Exclude all publications with 0 citations? This helps focus analysis on impactful papers.")) return;
            try {
              const res = await publicationsApi.bulkExclude(projectId, 0);
              toast.success(`${res.data.excluded_count} publications excluded.`);
              setExcludedCount(prev => prev + res.data.excluded_count);
              setPublications(prev => prev.map(p =>
                (p.citation_count === null || p.citation_count === 0) && !p.excluded ? { ...p, excluded: true } : p
              ));
            } catch { toast.error("Bulk exclude failed."); }
          }}
            disabled={total === 0 && !loading}
            className="flex items-center gap-2 px-4 py-2 bg-[#fef3c7] text-[#92400e] rounded-lg font-bold text-xs hover:bg-[#fde68a] transition disabled:opacity-40 disabled:cursor-not-allowed">
            <span className="material-symbols-outlined text-sm">filter_alt</span>
            Exclude 0-citation papers
          </button>
        </div>
        <button onClick={() => includedCount > 0 ? router.push(`/projects/${projectId}/dashboard`) : toast.error("No publications to analyze. Run a search first.")}
          disabled={includedCount === 0 && !loading}
          className="flex items-center gap-2 px-6 py-2.5 bg-[#001e4f] text-white rounded-lg font-bold text-sm hover:opacity-90 transition disabled:opacity-40 disabled:cursor-not-allowed">
          <span className="material-symbols-outlined text-sm">auto_awesome</span>
          Run Bibliometric Analysis
        </button>
      </div>

      {/* Publication Cards */}
      <div style={{ minHeight: "600px" }}>
      {loading ? (
        <div className="text-[#43474e] text-center py-20">Loading publications...</div>
      ) : publications.length === 0 ? (
        <div className="text-center py-20">
          <span className="material-symbols-outlined text-6xl text-[#c4c6cf] mb-4 block">search_off</span>
          <h3 className="text-xl font-bold text-[#191c1e] mb-2" style={{fontFamily:"'Manrope',sans-serif"}}>No Publications Found</h3>
          <p className="text-sm text-[#43474e] mb-6">Run a search first to populate results for this project.</p>
          <button onClick={() => router.push(`/projects/${projectId}/search`)}
            className="px-6 py-2.5 bg-[#001e4f] text-white rounded-lg font-bold text-sm hover:opacity-90 transition">
            Go to Search
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {publications.map((pub) => (
            <article key={pub.id} className={`group bg-white p-8 rounded-xl transition-all duration-300 hover:shadow-[0px_12px_32px_rgba(25,28,30,0.08)] border border-transparent hover:border-[#e6e8ea] ${pub.excluded ? "opacity-50" : ""}`}>
              <div className="flex items-start justify-between gap-6">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-[10px] font-bold py-1 px-2 bg-[#e6e8ea] rounded text-[#43474e] uppercase tracking-wider">
                      {pub.publication_type || "Article"}
                    </span>
                    {(pub.citation_count ?? 0) > 50 && (
                      <span className="text-[10px] font-bold py-1 px-2 bg-[#d9e2ff] text-[#001945] rounded uppercase tracking-wider">High Impact</span>
                    )}
                  </div>
                  <h3 className={`text-xl font-bold mb-3 leading-tight transition-colors ${pub.excluded ? "text-[#43474e] line-through" : "text-[#001e4f] group-hover:text-[#2b5bb5]"}`} style={{fontFamily:"'Manrope',sans-serif"}}>
                    {pub.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-y-2 text-sm text-[#43474e] font-medium">
                    <span className="text-[#191c1e] font-bold">
                      {pub.authors.slice(0, 2).map(a => a.name).join(", ")}{pub.authors.length > 2 ? " et al." : ""}
                    </span>
                    <span className="mx-2 text-[#c4c6cf]">•</span>
                    <span>{pub.journal_name || "Unknown"}</span>
                    <span className="mx-2 text-[#c4c6cf]">•</span>
                    <span>{pub.year}</span>
                  </div>
                </div>
                <div className="flex flex-col items-center gap-3 shrink-0">
                  <div className="flex flex-col items-center justify-center min-w-[64px] h-16 bg-[#eceef0] rounded-lg">
                    <span className="text-lg font-extrabold text-[#001e4f]">{pub.citation_count ?? 0}</span>
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
          <nav className="flex items-center gap-1 bg-[#eceef0] rounded-full px-2 py-1">
            <button onClick={() => setPage(Math.max(1, page - 1))} className="p-2 hover:bg-[#e6e8ea] rounded-full transition-colors">
              <span className="material-symbols-outlined text-sm">chevron_left</span>
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => i + 1).map((p) => (
              <button key={p} onClick={() => setPage(p)}
                className={`px-4 py-1.5 rounded-full text-xs font-bold ${page === p ? "bg-[#001e4f] text-white" : "hover:bg-[#e6e8ea]"}`}>
                {p}
              </button>
            ))}
            {totalPages > 5 && <span className="px-2 text-[#74777f] text-xs">...</span>}
            {totalPages > 5 && (
              <button onClick={() => setPage(totalPages)} className="px-4 py-1.5 hover:bg-[#e6e8ea] rounded-full text-xs font-bold">{totalPages}</button>
            )}
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} className="p-2 hover:bg-[#e6e8ea] rounded-full transition-colors">
              <span className="material-symbols-outlined text-sm">chevron_right</span>
            </button>
          </nav>
        </div>
      )}
    </div>
  );
}
