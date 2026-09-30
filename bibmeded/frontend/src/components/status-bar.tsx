import { Icon } from "@/components/ui";
import { ANALYSIS_MODULES, DATA_SOURCES, DOCS_URL, REPO_URL } from "@/lib/sources";

const LINK_CLASSES =
  "inline-flex items-center min-h-6 px-1 underline-offset-4 hover:underline hover:text-on-surface focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2 rounded-[var(--radius-xs)]";

export function StatusBar() {
  return (
    <footer
      aria-label="Application status"
      className="mt-auto px-4 md:px-10 lg:px-14 py-4 max-w-7xl w-full mx-auto rule-t flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-on-surface-subtle"
    >
      <span className="inline-flex items-center gap-1.5">
        <Icon name="shield" size={13} />
        Local workspace
      </span>
      <span className="inline-flex items-center gap-1.5">
        <Icon name="layers" size={13} />
        {DATA_SOURCES.length} sources · {ANALYSIS_MODULES.length} analyses
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span aria-hidden="true" className="w-1.5 h-1.5 rounded-full bg-accent" />
        Status: Ready
      </span>
      <span className="ml-auto inline-flex items-center gap-4">
        <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className={LINK_CLASSES}>
          Docs
        </a>
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className={LINK_CLASSES}>
          GitHub
        </a>
        <span className="font-display italic text-sm">MIT licensed</span>
      </span>
    </footer>
  );
}
