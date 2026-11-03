"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { publicationsApi, EXCLUSION_REASON_LABELS } from "@/lib/api";
import { ConfirmDialog } from "@/components/ui";

const CITATION_THRESHOLD = 0;
const BULK_REASON = "other" as const;
type Preview = { status: "counting" } | { status: "ready"; count: number; missing: number } | { status: "unavailable" };

function plural(count: number, noun: string) {
  return count.toLocaleString() + " " + noun + (count === 1 ? "" : "s");
}

interface BulkExcludeDialogProps {
  open: boolean;
  projectId: number;
  onCancel: () => void;
  onExcluded: () => void;
}

export function BulkExcludeDialog({ open, projectId, onCancel, onExcluded }: BulkExcludeDialogProps) {
  const [preview, setPreview] = useState<Preview>({ status: "counting" });
  useEffect(() => {
    if (!open) return;
    let stale = false;
    publicationsApi.list(projectId, { limit: 1 }).then((res) => {
      if (!stale) setPreview({ status: "ready", count: res.data.zero_citation_count, missing: res.data.missing_citation_count });
    }).catch(() => {
      if (!stale) setPreview({ status: "unavailable" });
    });
    return () => { stale = true; setPreview({ status: "counting" }); };
  }, [open, projectId]);

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
          <p>
            {preview.status === "ready"
              ? plural(preview.missing, "publication") + " with no citation count will be left unchanged."
              : "Publications with no citation count will be left unchanged."}
          </p>
          {count !== 0 && (
            <p>
              Each is recorded with the reason &ldquo;{EXCLUSION_REASON_LABELS[BULK_REASON]}&rdquo; at title/abstract screening in the PRISMA flow and methodology log, and
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
