"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/ui";

const projectNavItems = [
  { suffix: "search", icon: "search", label: "Search" },
  { suffix: "results", icon: "list_alt", label: "Results" },
  { suffix: "dashboard", icon: "analytics", label: "Dashboard" },
  { suffix: "export", icon: "download", label: "Export" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Close the drawer on nav — handled via each link's onClick (closeDrawer) rather
  // than a pathname effect, to avoid synchronous setState-in-effect (React Compiler
  // flags it as a cascading-render risk). Desktop is unaffected; the drawer only
  // exists below the md breakpoint.
  const closeDrawer = () => setOpen(false);

  // Escape closes the drawer on mobile for keyboard parity.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
      if (e.key === "Escape") triggerRef.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const projectMatch = pathname.match(/^\/projects\/(\d+)/);
  const projectId = projectMatch ? projectMatch[1] : null;

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const linkClasses = (active: boolean) =>
    [
      "flex items-center gap-3 px-4 py-2.5 rounded-[var(--radius-md)] text-sm",
      "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
      "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
      active
        ? "bg-surface-raised text-primary font-semibold elev-1"
        : "text-on-surface-muted hover:text-on-surface hover:bg-surface-hover font-medium",
    ].join(" ");

  return (
    <>
      {/* Mobile hamburger — fixed top-left, hidden above md where the sidebar is always-on. */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-label={open ? "Close navigation" : "Open navigation"}
        aria-expanded={open}
        aria-controls="primary-sidebar"
        className="md:hidden fixed top-3 left-3 z-50 inline-flex items-center justify-center w-11 h-11 rounded-[var(--radius-md)] bg-surface-raised border border-divider shadow-sm focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
      >
        <span className="material-symbols-outlined" aria-hidden="true">
          {open ? "close" : "menu"}
        </span>
      </button>

      {/* Backdrop only renders on mobile when open. */}
      {open && (
        <div
          aria-hidden="true"
          onClick={() => setOpen(false)}
          className="md:hidden fixed inset-0 z-30 bg-black/40"
        />
      )}

      <aside
        id="primary-sidebar"
        aria-label="Primary navigation"
        className={[
          "fixed left-0 top-0 h-full z-40 flex-col p-4",
          "bg-surface-sunken w-64 border-r border-divider",
          "transition-transform duration-200 ease-out",
          open ? "flex translate-x-0" : "hidden -translate-x-full",
          "md:flex md:translate-x-0",  // always visible above md
        ].join(" ")}
      >
        <div className="mb-8 px-4 pt-2">
          <Link
            href="/"
            onClick={closeDrawer}
            aria-label="BibMedEd — go to project list"
            className="inline-flex items-baseline gap-2 focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2 rounded-[var(--radius-sm)]"
          >
            <span className="block w-1.5 h-6 rounded-full bg-accent" aria-hidden="true" />
            <span
              className="text-xl font-extrabold tracking-tight text-primary"
              style={{ fontFamily: "var(--font-display)" }}
            >
              BibMedEd
            </span>
          </Link>
          <p className="text-[10px] uppercase tracking-[0.18em] text-on-surface-subtle font-bold mt-1.5 pl-3.5">
            Bibliometric Analysis
          </p>
        </div>

        <nav aria-label="Workspace" className="flex-1 flex flex-col gap-1" style={{ fontFamily: "var(--font-display)" }}>
          <Link
            href="/"
            onClick={closeDrawer}
            aria-current={pathname === "/" ? "page" : undefined}
            className={linkClasses(pathname === "/")}
          >
            <span className="material-symbols-outlined" aria-hidden="true">folder_open</span>
            Projects
          </Link>

          {projectId && (
            <>
              <p className="mt-6 mb-1 px-4 text-[10px] font-bold uppercase tracking-[0.18em] text-on-surface-subtle">
                Current project
              </p>
              {projectNavItems.map((item) => {
                const href = `/projects/${projectId}/${item.suffix}`;
                const active = isActive(href);
                return (
                  <Link
                    key={item.suffix}
                    href={href}
                    onClick={closeDrawer}
                    aria-current={active ? "page" : undefined}
                    className={linkClasses(active)}
                  >
                    <span className="material-symbols-outlined" aria-hidden="true">{item.icon}</span>
                    {item.label}
                  </Link>
                );
              })}
            </>
          )}
        </nav>

        <div className="mt-auto space-y-3">
          <div className="flex items-center justify-between px-2">
            <a
              href="https://github.com/ata381/BibMedEd"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Open BibMedEd on GitHub"
              className="inline-flex items-center justify-center w-10 h-10 rounded-[var(--radius-md)] text-on-surface-muted hover:text-on-surface hover:bg-surface-hover transition-colors focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
            >
              <span className="material-symbols-outlined" aria-hidden="true">code</span>
            </a>
            <a
              href="https://ata381.github.io/BibMedEd/"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Open documentation"
              className="inline-flex items-center justify-center w-10 h-10 rounded-[var(--radius-md)] text-on-surface-muted hover:text-on-surface hover:bg-surface-hover transition-colors focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
            >
              <span className="material-symbols-outlined" aria-hidden="true">menu_book</span>
            </a>
            <ThemeToggle />
          </div>

          <div className="p-3 bg-surface-raised rounded-[var(--radius-lg)] border border-divider">
            <div className="flex items-center gap-3">
              <div
                aria-hidden="true"
                className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center text-sm font-bold"
                style={{ fontFamily: "var(--font-display)" }}
              >
                R
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-on-surface truncate">Researcher</p>
                <p className="text-[10px] text-on-surface-muted truncate">Medical Education</p>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
