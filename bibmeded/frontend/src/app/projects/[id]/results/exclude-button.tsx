"use client";

import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { publicationsApi, Publication, ExclusionReason, EXCLUSION_REASON_LABELS } from "@/lib/api";
import { Icon } from "@/components/ui";
import { useReadOnly } from "@/lib/read-only";

const LABEL_TITLE_LENGTH = 60;
const MENU_KEYS = ["ArrowDown", "ArrowUp", "Home", "End"];

interface ExcludeButtonProps {
  pub: Publication;
  projectId: number;
  onToggle: (id: number, excluded: boolean, reason: ExclusionReason | null) => void;
}

export function ExcludeButton({ pub, projectId, onToggle }: ExcludeButtonProps) {
  const [showMenu, setShowMenu] = useState(false);
  const readOnly = useReadOnly() !== false;
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);

  // Close on outside click. `click` (not `mousedown`) so the trigger's own
  // handler can close-then-reopen-then-close without racing.
  useEffect(() => {
    if (!showMenu) return;
    const onDocClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setShowMenu(false);
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
    if (pub.excluded) doToggle();
    else setShowMenu((v) => !v);
  };

  const handleMenuKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!MENU_KEYS.includes(e.key)) return;
    e.preventDefault();
    const items = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>("[role='menuitem']"));
    if (items.length === 0) return;
    const current = Math.max(0, items.indexOf(document.activeElement as HTMLButtonElement));
    const next =
      e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (current + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items[next].focus();
  };

  // Truncated title in the accessible name so a screen reader announcing 20
  // identical "Included" buttons gets enough context to disambiguate.
  const labelTitle = (pub.title || "Untitled").slice(0, LABEL_TITLE_LENGTH);
  const triggerLabel = pub.excluded ? `Re-include "${labelTitle}"` : `Exclude "${labelTitle}" — open PRISMA reason picker`;

  return (
    <div className="relative flex flex-col items-end" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={handlePrimary}
        disabled={readOnly}
        aria-label={readOnly ? `${pub.excluded ? "Excluded" : "Included"}: "${labelTitle}"` : triggerLabel}
        aria-haspopup={!pub.excluded ? "menu" : undefined}
        aria-expanded={!pub.excluded ? showMenu : undefined}
        className={[
          "inline-flex items-center gap-1.5 h-9 px-3 rounded-[var(--radius-md)] border text-xs font-bold uppercase tracking-[0.08em] cursor-pointer",
          "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
          "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
          "disabled:cursor-default disabled:hover:border-transparent",
          pub.excluded
            ? "bg-danger-container text-danger border-transparent hover:border-danger"
            : "bg-accent-container text-on-accent-container border-transparent hover:border-accent",
        ].join(" ")}
      >
        <Icon name={pub.excluded ? "xCircle" : "checkCircle"} size={15} />
        {pub.excluded ? "Excluded" : "Included"}
      </button>
      {pub.excluded && pub.exclusion_reason && (
        <span className="mt-1.5 text-xs text-on-surface-muted text-right max-w-[11rem] leading-snug">
          {EXCLUSION_REASON_LABELS[pub.exclusion_reason]}
        </span>
      )}
      {showMenu && !pub.excluded && (
        <div
          role="menu"
          aria-label="Select exclusion reason"
          onKeyDown={handleMenuKeyDown}
          className="absolute right-0 top-full mt-1 w-72 bg-surface-raised rounded-[var(--radius-md)] elev-3 border border-divider z-10 py-1 text-sm"
        >
          <p className="eyebrow px-3 pt-2 pb-1.5">Exclude — PRISMA reason</p>
          {(Object.keys(EXCLUSION_REASON_LABELS) as ExclusionReason[]).map((code, idx) => (
            <button
              key={code}
              ref={idx === 0 ? firstItemRef : undefined}
              autoFocus={idx === 0}
              type="button"
              role="menuitem"
              onClick={(e) => {
                e.stopPropagation();
                doToggle(code);
              }}
              className="block w-full min-h-9 text-left px-3 py-2 text-on-surface hover:bg-surface-hover focus:bg-surface-hover focus:outline-none cursor-pointer"
            >
              {EXCLUSION_REASON_LABELS[code]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
