"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { publicationsApi, searchApi, Publication, SearchStatus, ExclusionReason } from "@/lib/api";
import { Badge, Button, Card, EmptyState, Icon, LoadingState, PageHeader, Skeleton, Stat } from "@/components/ui";
import { ExcludeButton } from "./exclude-button";
import { BulkExcludeDialog } from "./bulk-exclude-dialog";
import { useReadOnly } from "@/lib/read-only";

const PAGE_SIZE = 20;
const PAGE_WINDOW = 5;
const HIGH_IMPACT_THRESHOLD = 50;

const PAGE_BUTTON = (active: boolean) =>
  [
    "min-w-10 h-10 px-3 rounded-[var(--radius-md)] text-sm font-semibold tabular-nums cursor-pointer transition-colors",
    "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
    active ? "bg-ink text-on-ink" : "text-on-surface-muted hover:bg-surface-hover hover:text-on-surface",
  ].join(" ");

function pageWindowFor(page: number, totalPages: number) {
  if (totalPages <= PAGE_WINDOW) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const half = Math.floor(PAGE_WINDOW / 2);
  const end = Math.min(totalPages, Math.max(1, page - half) + PAGE_WINDOW - 1);
  const start = Math.max(1, end - PAGE_WINDOW + 1);
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}

export default function ResultsReview() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Number(params.id);
  const readOnly = useReadOnly() !== false;
  const [publications, setPublications] = useState<Publication[]>([]);
  const [total, setTotal] = useState(0);
  const [excludedCount, setExcludedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchStats, setSearchStats] = useState<SearchStatus | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const includedCount = total - excludedCount;
  const refresh = () => setRefreshTick((t) => t + 1);

  const handleToggleExclude = (pubId: number, excluded: boolean, reason: ExclusionReason | null) => {
    setPublications((prev) => prev.map((p) => (p.id === pubId ? { ...p, excluded, exclusion_reason: reason } : p)));
    setExcludedCount((prev) => (excluded ? prev + 1 : prev - 1));
  };

  useEffect(() => {
    searchApi.latest(projectId).then((res) => setSearchStats(res.data)).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    // One-shot loading flag per fetch; the abort controller keeps a fast
    // pagination click from clobbering excludedCount with stale data.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    const ctrl = new AbortController();
    publicationsApi
      .list(projectId, { sort_by: "citation_count", order: "desc", limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE })
      .then((res) => {
        if (ctrl.signal.aborted) return;
        setPublications(res.data.items);
        setTotal(res.data.total);
        setExcludedCount(res.data.excluded_count ?? 0);
      })
      .catch(() => {
        if (!ctrl.signal.aborted) toast.error("Failed to load publications.");
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [projectId, page, refreshTick]);

  const [bulkExcludeOpen, setBulkExcludeOpen] = useState(false);

  const goToAnalysis = () => {
    if (includedCount > 0) router.push(`/projects/${projectId}/dashboard`);
    else toast.error("No publications to analyze. Run a search first.");
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageWindow = pageWindowFor(page, totalPages);
  const raw = searchStats?.raw_result_count ?? 0;
  const duplicates = searchStats?.duplicate_count ?? 0;
  // `result_count` is records persisted; `duplicate_count` is records removed by
  // cross-source dedup — their sum is what the pipeline saw. Under-triggers on
  // re-runs over an existing corpus, never over-triggers.
  const seen = (searchStats?.result_count ?? 0) + duplicates;
  const truncated = raw > 0 && seen > 0 && raw > seen;

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Step 2 · Screening"
        title="Results review"
        lede={
          <>
            <span className="numeral text-on-surface text-xl">{total.toLocaleString()}</span> unique publications after cross-source
            deduplication. Exclude records with a PRISMA reason — every decision is counted in the flow diagram and the methodology log.
          </>
        }
        aside={
          <Button onClick={goToAnalysis} disabled={includedCount === 0 && !loading} trailingIcon="arrowRight">
            Run Bibliometric Analysis
          </Button>
        }
      />

      {truncated && (
        <div role="status" className="flex items-start gap-3 rounded-[var(--radius-md)] border border-warning/40 bg-warning-container px-5 py-4">
          <Icon name="alert" size={20} className="text-warning mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-on-surface">
              Search returned {raw.toLocaleString()} records — only the first {seen.toLocaleString()} were fetched.
            </p>
            <p className="text-sm text-on-surface-muted mt-1 max-w-prose">
              The remainder were not retrieved. For PRISMA / journal submissions, rerun the search with a higher{" "}
              <code className="font-mono text-xs">max_results</code> or narrow the query — silently truncating a systematic review&apos;s record set is
              not journal-acceptable.
            </p>
          </div>
        </div>
      )}

      <section
        aria-label={`PRISMA flow: ${raw.toLocaleString()} identified, ${duplicates} duplicates removed, ${excludedCount} manually excluded, ${includedCount.toLocaleString()} included`}
      >
        <div className="flex items-baseline justify-between gap-4 mb-4">
          <h2 className="text-2xl text-on-surface">PRISMA flow</h2>
          <Badge tone="primary">Identification → Screening</Badge>
        </div>
        <div
          tabIndex={0}
          role="region"
          aria-label="PRISMA screening counts"
          className="flex items-stretch gap-3 overflow-x-auto pb-2 -mx-1 px-1 rule-t rule-b py-6 focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2 rounded-[var(--radius-sm)]"
        >
          <FlowStep>
            <Stat label="Records identified" value={searchStats?.raw_result_count?.toLocaleString() ?? "—"} note="via database search" />
          </FlowStep>
          <FlowArrow />
          <FlowStep>
            <Stat
              label="Duplicates removed"
              tone="danger"
              value={searchStats?.duplicate_count == null ? "—" : duplicates === 0 ? "0" : `−${duplicates}`}
              note="Matched by exact PMID and DOI cross-check"
            />
          </FlowStep>
          {excludedCount > 0 && (
            <>
              <FlowArrow />
              <FlowStep>
                <Stat label="Manually excluded" tone="warning" value={`−${excludedCount}`} note="by reviewer, with PRISMA reason" />
              </FlowStep>
            </>
          )}
          <FlowArrow />
          <FlowStep emphasis>
            <Stat label="Records included" tone="primary" value={includedCount.toLocaleString()} note="carried into analysis" />
          </FlowStep>
        </div>
      </section>

      <section aria-labelledby="publications-heading">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 id="publications-heading" className="text-2xl text-on-surface">
            Publications
            <span className="ml-3 text-sm font-sans font-normal text-on-surface-subtle tabular-nums">
              sorted by citations · page {page} of {totalPages}
            </span>
          </h2>
          {!readOnly && <Button variant="outline" size="sm" leadingIcon="filter" onClick={() => setBulkExcludeOpen(true)} disabled={total === 0 && !loading}>
            Exclude 0-citation papers
          </Button>}
        </div>

        <div className="min-h-[24rem]">
          {loading ? (
            <LoadingState label="Loading publications" className="space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-28" />
              ))}
            </LoadingState>
          ) : publications.length === 0 ? (
            <Card>
              <EmptyState
                icon="searchOff"
                title="No publications found"
                description="Run a search first to populate results for this project."
                action={<Button onClick={() => router.push(`/projects/${projectId}/search`)}>Go to Search</Button>}
              />
            </Card>
          ) : (
            <ol className="rule-t">
              {publications.map((pub, i) => (
                <PublicationRow key={pub.id} pub={pub} index={(page - 1) * PAGE_SIZE + i + 1} projectId={projectId} onToggle={handleToggleExclude} />
              ))}
            </ol>
          )}
        </div>
        <BulkExcludeDialog
          open={bulkExcludeOpen}
          projectId={projectId}
          total={total}
          loaded={publications}
          onCancel={() => setBulkExcludeOpen(false)}
          onExcluded={() => {
            setBulkExcludeOpen(false);
            refresh();
          }}
        />
      </section>

      {totalPages > 1 && (
        <nav aria-label="Pagination" className="flex justify-center">
          <div className="inline-flex items-center gap-1 rounded-[var(--radius-lg)] border border-divider bg-surface-raised p-1">
            <button
              type="button"
              onClick={() => setPage(Math.max(1, page - 1))}
              aria-label="Previous page"
              disabled={page === 1}
              className={`${PAGE_BUTTON(false)} disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              <Icon name="chevronLeft" size={16} />
            </button>
            {pageWindow[0] > 1 && (
              <>
                <button type="button" onClick={() => setPage(1)} aria-label="Page 1" className={PAGE_BUTTON(false)}>
                  1
                </button>
                {pageWindow[0] > 2 && <span aria-hidden="true" className="px-1 text-on-surface-subtle">…</span>}
              </>
            )}
            {pageWindow.map((p) => (
              <button key={p} type="button" onClick={() => setPage(p)} aria-label={`Page ${p}`} aria-current={page === p ? "page" : undefined} className={PAGE_BUTTON(page === p)}>
                {p}
              </button>
            ))}
            {pageWindow[pageWindow.length - 1] < totalPages && (
              <>
                {pageWindow[pageWindow.length - 1] < totalPages - 1 && <span aria-hidden="true" className="px-1 text-on-surface-subtle">…</span>}
                <button type="button" onClick={() => setPage(totalPages)} aria-label={`Page ${totalPages}`} className={PAGE_BUTTON(false)}>
                  {totalPages}
                </button>
              </>
            )}
            <button
              type="button"
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              aria-label="Next page"
              disabled={page === totalPages}
              className={`${PAGE_BUTTON(false)} disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              <Icon name="chevronRight" size={16} />
            </button>
          </div>
        </nav>
      )}
    </div>
  );
}

function FlowStep({ children, emphasis = false }: { children: React.ReactNode; emphasis?: boolean }) {
  return (
    <div
      className={`shrink-0 min-w-[11rem] flex-1 rounded-[var(--radius-md)] px-5 py-4 ${
        emphasis ? "bg-surface-raised border border-primary/40" : "bg-surface-raised border border-divider"
      }`}
    >
      {children}
    </div>
  );
}

function FlowArrow() {
  return (
    <span aria-hidden="true" className="self-center shrink-0 text-on-surface-subtle">
      <Icon name="arrowRight" size={18} />
    </span>
  );
}

function PublicationRow({
  pub,
  index,
  projectId,
  onToggle,
}: {
  pub: Publication;
  index: number;
  projectId: number;
  onToggle: (id: number, excluded: boolean, reason: ExclusionReason | null) => void;
}) {
  const authors = pub.authors.slice(0, 3).map((a) => a.name).join(", ") + (pub.authors.length > 3 ? " et al." : "");
  return (
    <li>
      <article
        aria-labelledby={`pub-title-${pub.id}`}
        className={`grid grid-cols-[2.5rem_1fr] md:grid-cols-[2.5rem_1fr_auto] gap-x-4 gap-y-3 py-6 rule-b transition-opacity ${pub.excluded ? "opacity-60" : ""}`}
      >
        <span className="numeral text-lg text-on-surface-subtle pt-1">{String(index).padStart(2, "0")}</span>
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <Badge>{pub.publication_type || "Article"}</Badge>
            {(pub.citation_count ?? 0) > HIGH_IMPACT_THRESHOLD && <Badge tone="primary">High impact</Badge>}
            {pub.excluded && <Badge tone="danger">Excluded</Badge>}
          </div>
          <h3 id={`pub-title-${pub.id}`} className={`text-xl leading-snug ${pub.excluded ? "text-on-surface-muted line-through" : "text-on-surface"}`}>
            {pub.title}
          </h3>
          <p className="mt-2 text-sm text-on-surface-muted leading-relaxed">
            <span className="text-on-surface font-semibold">{authors}</span>
            <span aria-hidden="true"> · </span>
            <span className="font-display italic text-base">{pub.journal_name || "Unknown journal"}</span>
            <span aria-hidden="true"> · </span>
            <span className="tabular-nums">{pub.year ?? "n.d."}</span>
            {pub.doi ? (
              <>
                <span aria-hidden="true"> · </span>
                <span className="font-mono text-xs">doi:{pub.doi}</span>
              </>
            ) : null}
          </p>
        </div>
        <div className="col-start-2 md:col-start-3 flex md:flex-col items-center md:items-end justify-between md:justify-start gap-3 md:min-w-[9rem]">
          <p className="text-right">
            <span className="numeral text-2xl text-on-surface tabular-nums">{pub.citation_count ?? 0}</span>
            <span className="block eyebrow">citations</span>
          </p>
          <ExcludeButton pub={pub} projectId={projectId} onToggle={onToggle} />
        </div>
      </article>
    </li>
  );
}
