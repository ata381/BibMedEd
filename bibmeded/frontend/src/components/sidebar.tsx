"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, ThemeToggle, type IconName } from "@/components/ui";
import { DOCS_URL, REPO_URL, WORKFLOW_STEPS } from "@/lib/sources";

const STEP_ICONS: Record<(typeof WORKFLOW_STEPS)[number]["suffix"], IconName> = {
  search: "search",
  results: "list",
  dashboard: "chart",
  export: "download",
};

const ICON_LINK_CLASSES = [
  "inline-flex items-center justify-center w-10 h-10 rounded-[var(--radius-md)]",
  "text-on-surface-muted hover:text-on-surface hover:bg-surface-hover transition-colors",
  "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
].join(" ");

function navLinkClasses(active: boolean) {
  return [
    "group flex items-center gap-3 pl-3 pr-3 h-11 -ml-px border-l-2 text-sm",
    "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
    "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:-outline-offset-2 focus-visible:rounded-[var(--radius-sm)]",
    active
      ? "border-primary text-on-surface font-semibold bg-surface-raised"
      : "border-transparent text-on-surface-muted hover:text-on-surface hover:border-outline font-medium",
  ].join(" ");
}

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // The drawer closes on each link's onClick rather than a pathname effect to
  // avoid a synchronous setState-in-effect cascade (React Compiler warning).
  const closeDrawer = () => setOpen(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const projectMatch = pathname.match(/^\/projects\/(\d+)/);
  const projectId = projectMatch ? projectMatch[1] : null;
  const isHome = pathname === "/";

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close navigation" : "Open navigation"}
        aria-expanded={open}
        aria-controls="primary-sidebar"
        className="md:hidden fixed top-3 left-3 z-50 inline-flex items-center justify-center w-11 h-11 rounded-[var(--radius-md)] bg-surface-raised border border-divider elev-1 focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
      >
        <Icon name={open ? "close" : "menu"} size={20} />
      </button>

      {open && (
        <div aria-hidden="true" onClick={() => setOpen(false)} className="md:hidden fixed inset-0 z-30 bg-overlay" />
      )}

      <aside
        id="primary-sidebar"
        aria-label="Primary navigation"
        className={[
          "fixed left-0 top-0 h-full z-40 flex-col w-[17rem]",
          "bg-surface-sunken border-r border-divider",
          "transition-transform duration-[var(--duration-base)] ease-[var(--ease-decelerate)]",
          open ? "flex translate-x-0" : "hidden -translate-x-full",
          "md:flex md:translate-x-0",
        ].join(" ")}
      >
        <div className="px-6 pt-7 pb-6">
          <Link
            href="/"
            onClick={closeDrawer}
            aria-label="BibMedEd — go to project list"
            className="group inline-flex flex-col focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-4 rounded-[var(--radius-sm)]"
          >
            <span className="block h-[3px] w-10 bg-primary mb-3 transition-[width] duration-[var(--duration-base)] group-hover:w-14" aria-hidden="true" />
            <span className="font-display text-[1.75rem] leading-none font-semibold tracking-[-0.01em] text-on-surface">
              BibMedEd
            </span>
          </Link>
          <p className="eyebrow mt-3">Bibliometrics for medical education</p>
        </div>

        <nav aria-label="Workspace" className="flex flex-col px-4 gap-1 border-l border-divider ml-6 mr-2 self-stretch">
          <Link href="/" onClick={closeDrawer} aria-current={isHome ? "page" : undefined} className={navLinkClasses(isHome)}>
            <Icon name="folder" size={17} className={isHome ? "text-primary" : "text-on-surface-subtle group-hover:text-on-surface"} />
            Projects
          </Link>

          {projectId && (
            <>
              <p className="eyebrow mt-7 mb-2 pl-3">Current project</p>
              {WORKFLOW_STEPS.map((step, i) => {
                const href = `/projects/${projectId}/${step.suffix}`;
                const active = pathname.startsWith(href);
                return (
                  <Link
                    key={step.suffix}
                    href={href}
                    onClick={closeDrawer}
                    aria-current={active ? "page" : undefined}
                    className={navLinkClasses(active)}
                  >
                    <span
                      aria-hidden="true"
                      className={`numeral w-5 text-xs tabular-nums ${active ? "text-primary" : "text-on-surface-subtle"}`}
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="flex-1">{step.label}</span>
                    <Icon name={STEP_ICONS[step.suffix]} size={15} className={active ? "text-primary" : "text-on-surface-subtle opacity-0 group-hover:opacity-100 transition-opacity"} />
                  </Link>
                );
              })}
            </>
          )}
        </nav>

        <div className="mt-auto px-5 pb-5 space-y-4">
          <div className="flex items-center gap-1">
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" aria-label="Open BibMedEd on GitHub" className={ICON_LINK_CLASSES}>
              <Icon name="github" size={18} />
            </a>
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" aria-label="Open documentation" className={ICON_LINK_CLASSES}>
              <Icon name="book" size={18} />
            </a>
            <ThemeToggle className="ml-auto" />
          </div>
          <p className="rule-t pt-4 text-xs leading-relaxed text-on-surface-subtle">
            Self-hosted. Your searches and records stay on this machine.
          </p>
        </div>
      </aside>
    </>
  );
}
