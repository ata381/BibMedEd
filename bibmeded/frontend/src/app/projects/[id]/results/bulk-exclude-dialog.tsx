"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { publicationsApi, Publication, EXCLUSION_REASON_LABELS } from "@/lib/api";
import { ConfirmDialog } from "@/components/ui";

const CITATION_THRESHOLD = 0;
const BULK_REASON = "other" as const;
// The list endpoint caps `limit` at 500 and has no unique sort key, so offset
// paging can skip or repeat tied rows; above this we can't count exactly.
const MAX_COUNTABLE = 500;

type Preview = { status: "counting" } | { status: "ready"; count: number } | { status: "unavailable" };

function isBulkExcludable(pub: Publication) {
  return !pub.excluded && (pub.citation_count ?? 0) <= CITATION_THRESHOLD;
}

function plural(count: number, noun: string) {
  return `${count.toLocaleString()} ${noun}${count === 1 ? "" : "s"}`;
}

interface BulkExcludeDialogProps {
  open: boolean;
  projectId: number;
  total: number;
  /** Publications already on screen; used directly when they cover the whole project. */
  loaded: Publication[];
  onCancel: () => void;
  onExcluded: () => void;
}

export function BulkExcludeDialog({ open, projectId, total, loaded, onCancel, onExcluded }: BulkExcludeDialogProps) {
  const [fetched, setFetched] = useState<number | "failed" | null>(null);
  const coversProject = loaded.length >= total;
  const needsFetch = !coversProject && total <= MAX_COUNTABLE;

  useEffect(() => {
    if (!open || !needsFetch) return;
    let stale = false;
    publicationsApi
      .list(projectId, { sort_by: "citation_count", order: "asc", limit: MAX_COUNTABLE, offset: 0 })
      .then((res) => {
        if (!stale) setFetched(res.data.items.filter(isBulkExcludable).length);
      })
      .catch(() => {
        if (!stale) setFetched("failed");
      });
    return () => {
      stale = true;
      setFetched(null);
    };
  }, [open, needsFetch, projectId]);

  const preview: Preview = coversProject
    ? { status: "ready", count: loaded.filter(isBulkExcludable).length }
    : !needsFetch || fetched === "failed"
      ? { status: "unavailable" }
      : fetched === null
        ? { status: "counting" }
        : { status: "ready", count: fetched };

  const handleConfirm = async () => {
    try {
      const res = await publicationsApi.bulkExclude(projectId, CITATION_THRESHOLD, BULK_REASON);
      toast.success(`${plural(res.data.excluded_count, "publication")} excluded.`);
      onExcluded();
    } catch {
      toast.error("Bulk exclude failed.");
    }
  };

  const count = preview.status === "ready" ? preview.count : null;

  return (
    <ConfirmDialog
      open={open}
      tone="danger"
      title="Exclude uncited publications?"
      description={
        <>
          <p aria-live="polite">
            {preview.status === "counting" ? (
              "Counting publications with 0 citations…"
            ) : count === null ? (
              "Every included publication with 0 citations will be excluded."
            ) : count === 0 ? (
              "No included publications have 0 citations, so nothing will change."
            ) : (
              <>
                <strong className="font-semibold text-on-surface">{plural(count, "publication")} will be excluded</strong> for having 0
                citations.
              </>
            )}
          </p>
          {count !== 0 && (
            <p>
              Each is recorded with the reason &ldquo;{EXCLUSION_REASON_LABELS[BULK_REASON]}&rdquo; in the PRISMA flow and methodology log, and
              can be re-included individually afterwards.
            </p>
          )}
        </>
      }
      confirmLabel={count ? `Exclude ${plural(count, "publication")}` : "Exclude uncited publications"}
      onConfirm={handleConfirm}
      onCancel={onCancel}
    />
  );
}
