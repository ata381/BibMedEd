"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { publicationsApi, Publication } from "@/lib/api";

export default function ResultsReview() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);
  const [publications, setPublications] = useState<Publication[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const limit = 20;

  useEffect(() => {
    setLoading(true);
    publicationsApi.list(projectId, { sort_by: "citation_count", order: "desc", limit, offset: (page - 1) * limit })
      .then((res) => { setPublications(res.data.items); setTotal(res.data.total); })
      .catch(() => {})
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

      {/* Stats Row */}
      <div className="grid grid-cols-12 gap-6 mb-10">
        <div className="col-span-12 md:col-span-8 bg-white p-6 rounded-xl flex items-center justify-between shadow-[0px_12px_32px_rgba(25,28,30,0.06)]">
          <div className="flex items-center gap-5">
            <div className="w-12 h-12 bg-[#93f2f2] flex items-center justify-center rounded-full">
              <span className="material-symbols-outlined text-[#002020]">cleaning_services</span>
            </div>
            <div>
              <h4 className="font-bold text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>Deduplication Complete</h4>
              <p className="text-sm text-[#43474e]">Automated merging of cross-journal overlaps</p>
            </div>
          </div>
          <span className="px-3 py-1 bg-[#93f2f2] text-[#002020] text-[10px] font-bold uppercase tracking-widest rounded-full">PubMed</span>
        </div>
        <div className="col-span-12 md:col-span-4 bg-[#001e4f] text-white p-6 rounded-xl flex flex-col justify-between relative overflow-hidden">
          <div className="z-10">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-80">Total Results</p>
            <h3 className="text-3xl font-extrabold mt-1" style={{fontFamily:"'Manrope',sans-serif"}}>{total}</h3>
          </div>
          <div className="absolute -right-4 -bottom-4 opacity-10">
            <span className="material-symbols-outlined text-[80px]">verified_user</span>
          </div>
        </div>
      </div>

      {/* Analyze Button */}
      <div className="flex justify-end mb-6">
        <button onClick={() => router.push(`/projects/${projectId}/dashboard`)}
          className="flex items-center gap-2 px-6 py-2.5 bg-[#001e4f] text-white rounded-lg font-bold text-sm hover:opacity-90 transition">
          <span className="material-symbols-outlined text-sm">auto_awesome</span>
          Run Bibliometric Analysis
        </button>
      </div>

      {/* Publication Cards */}
      {loading ? (
        <div className="text-[#43474e] text-center py-20">Loading publications...</div>
      ) : (
        <div className="space-y-4">
          {publications.map((pub) => (
            <article key={pub.id} className="group bg-white p-8 rounded-xl transition-all duration-300 hover:shadow-[0px_12px_32px_rgba(25,28,30,0.08)] border border-transparent hover:border-[#e6e8ea] cursor-pointer">
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
                  <h3 className="text-xl font-bold text-[#001e4f] mb-3 leading-tight group-hover:text-[#2b5bb5] transition-colors" style={{fontFamily:"'Manrope',sans-serif"}}>
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
                <div className="flex flex-col items-end gap-3">
                  <div className="flex flex-col items-center justify-center min-w-[64px] h-16 bg-[#eceef0] rounded-lg">
                    <span className="text-lg font-extrabold text-[#001e4f]">{pub.citation_count ?? 0}</span>
                    <span className="text-[8px] font-bold uppercase tracking-tighter opacity-60">Citations</span>
                  </div>
                  <button className="text-[#43474e] hover:text-[#001e4f] transition-colors">
                    <span className="material-symbols-outlined">bookmark</span>
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

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
