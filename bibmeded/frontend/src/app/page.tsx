"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { projectsApi, Project } from "@/lib/api";
import { useReadOnly } from "@/lib/read-only";
import { ANALYSIS_MODULES, DATA_SOURCES, WORKFLOW_STEPS } from "@/lib/sources";
import { NetworkFigure } from "@/components/network-figure";
import { Button, ButtonLink, Icon, LoadingState, PageHeader, Skeleton, Stat, StatRow } from "@/components/ui";

const HEADLINE = (
  <>
    Reproducible bibliometrics for <span className="italic text-primary">medical education</span>.
  </>
);

const LEDE =
  "Search five literature databases at once, deduplicate by DOI and PMID, run six analyses, and export a PRISMA-ready methodology log — from one self-hosted tool.";

export default function Home() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingSample, setCreatingSample] = useState(false);
  const readOnly = useReadOnly() !== false;

  useEffect(() => {
    projectsApi
      .list()
      .then((res) => setProjects(res.data))
      .catch(() => toast.error("Failed to load projects. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = (project: Project) => {
    if (!confirm(`Delete project "${project.name}"? This will permanently remove all searches, publications, and analyses.`)) return;
    projectsApi
      .delete(project.id)
      .then(() => {
        setProjects((prev) => prev.filter((p) => p.id !== project.id));
        toast.success("Project deleted");
      })
      .catch(() => toast.error("Failed to delete project"));
  };

  const handleCreateSample = async () => {
    if (readOnly) return;
    setCreatingSample(true);
    try {
      const res = await projectsApi.createSample();
      toast.success("Sample project ready — no external search required.");
      router.push(`/projects/${res.data.id}/dashboard`);
    } catch {
      toast.error("Failed to create sample project.");
      setCreatingSample(false);
    }
  };

  const isEmpty = !loading && projects.length === 0;

  return (
    <div className="space-y-12">
      {isEmpty ? (
        <EmptyWorkspace creatingSample={creatingSample} onCreateSample={handleCreateSample} readOnly={readOnly} />
      ) : (
        <PageHeader
          eyebrow="Workspace"
          title={HEADLINE}
          lede={LEDE}
          aside={readOnly ? undefined : <ButtonLink href="/projects/new" leadingIcon="plus">New project</ButtonLink>}
        />
      )}

      {!isEmpty && (
        <section aria-labelledby="projects-heading">
          <div className="flex items-baseline justify-between mb-4">
            <h2 id="projects-heading" className="text-2xl text-on-surface">
              Projects
            </h2>
            <span className="text-sm text-on-surface-subtle tabular-nums">{loading ? "—" : `${projects.length} total`}</span>
          </div>

          {loading ? (
            <LoadingState label="Loading projects" className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-20" />
              ))}
            </LoadingState>
          ) : (
            <ol className="rule-t">
              {projects.map((project) => (
                <ProjectRow key={project.id} project={project} onDelete={readOnly ? undefined : handleDelete} />
              ))}
            </ol>
          )}

          {!readOnly && <div className="mt-6 flex flex-wrap items-center gap-3">
            <ButtonLink href="/projects/new" variant="outline" leadingIcon="plus">
              New project
            </ButtonLink>
            <Button variant="ghost" leadingIcon="flask" onClick={handleCreateSample} loading={creatingSample} disabled={creatingSample}>
              {creatingSample ? "Building sample project…" : "Explore sample project"}
            </Button>
          </div>}
        </section>
      )}
    </div>
  );
}

function EmptyWorkspace({ creatingSample, onCreateSample, readOnly }: { creatingSample: boolean; onCreateSample: () => void; readOnly: boolean }) {
  return (
    <>
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center pt-2">
        <div className="lg:col-span-7 max-w-2xl">
          <p className="eyebrow mb-4 rise" style={{ "--rise-index": 0 } as React.CSSProperties}>
            Workspace · Open source · Self-hosted
          </p>
          <h1 className="text-4xl md:text-5xl lg:text-[3.6rem] leading-[1.02] text-on-surface rise" style={{ "--rise-index": 1 } as React.CSSProperties}>
            {HEADLINE}
          </h1>
          <p className="mt-5 text-lg text-on-surface-muted leading-relaxed rise" style={{ "--rise-index": 2 } as React.CSSProperties}>
            {LEDE}
          </p>
          {!readOnly && <div className="mt-8 flex flex-col sm:flex-row sm:items-center gap-3 rise" style={{ "--rise-index": 3 } as React.CSSProperties}>
            <Button size="lg" leadingIcon="flask" onClick={onCreateSample} loading={creatingSample} disabled={creatingSample}>
              {creatingSample ? "Building sample project…" : "Explore sample project"}
            </Button>
            <ButtonLink href="/projects/new" size="lg" variant="outline" leadingIcon="plus">
              New project
            </ButtonLink>
          </div>}
          <p className="mt-4 text-sm text-on-surface-subtle rise" style={{ "--rise-index": 4 } as React.CSSProperties}>
            The sample is a synthetic corpus of 12 records — no API key, no network request, fully editable.
          </p>
        </div>
        <figure className="lg:col-span-5 rise" style={{ "--rise-index": 2 } as React.CSSProperties}>
          <div className="rounded-[var(--radius-lg)] border border-divider bg-surface-raised p-3 elev-2">
            <NetworkFigure />
          </div>
          <figcaption className="mt-3 text-sm text-on-surface-subtle font-display italic">
            Figure 1. Co-authorship network of the bundled sample corpus (illustrative).
          </figcaption>
        </figure>
      </section>

      <StatRow ariaLabel="What BibMedEd includes">
        <Stat label="Data sources" value={String(DATA_SOURCES.length).padStart(2, "0")} note={DATA_SOURCES.join(" · ")} />
        <Stat label="Analysis modules" value={String(ANALYSIS_MODULES.length).padStart(2, "0")} note={ANALYSIS_MODULES.join(" · ")} />
        <Stat label="Deduplication" value={<span className="text-2xl">DOI &amp; PMID</span>} note="Exact cross-source matching, counted in the PRISMA flow" />
        <Stat label="Exports" value={<span className="text-2xl">CSV · RIS · JSON</span>} note="Plus the methodology log, PRISMA 2020 SVG, and a zip bundle" />
      </StatRow>

      <section aria-labelledby="how-heading">
        <h2 id="how-heading" className="text-2xl text-on-surface mb-5">
          How a project runs
        </h2>
        <ol className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-x-8 gap-y-6 rule-t pt-6">
          {WORKFLOW_STEPS.map((step, i) => (
            <li key={step.suffix} className="flex gap-4">
              <span className="numeral text-3xl text-primary leading-none">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <p className="font-semibold text-on-surface">{step.label}</p>
                <p className="mt-1 text-sm text-on-surface-muted leading-relaxed">{step.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}

function yearOf(date: string | null) {
  return date ? new Date(date).getFullYear() : "—";
}

function ProjectRow({ project, onDelete }: { project: Project; onDelete?: (p: Project) => void }) {
  return (
    <li className="group relative grid grid-cols-[1fr_3rem] md:grid-cols-[1fr_9rem_8rem_3rem] items-center gap-x-6 gap-y-3 py-5 rule-b transition-colors hover:bg-surface-raised/70 -mx-3 px-3 rounded-[var(--radius-sm)]">
      <div className="min-w-0">
        <h3 className="text-xl leading-snug">
          <Link
            href={`/projects/${project.id}/results`}
            aria-label={`Open project ${project.name}`}
            className="text-on-surface hover:text-primary transition-colors after:absolute after:inset-0 after:content-[''] focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-4 rounded-[var(--radius-sm)]"
          >
            {project.name}
          </Link>
        </h3>
        <p className="mt-1 text-sm text-on-surface-muted line-clamp-2 leading-relaxed">
          {project.description || "No description provided"}
        </p>
      </div>
      {onDelete ? <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onDelete(project);
        }}
        aria-label={`Delete project ${project.name}`}
        className="md:order-last relative z-10 justify-self-end self-start md:self-center inline-flex items-center justify-center w-10 h-10 rounded-[var(--radius-md)] text-on-surface-subtle hover:text-danger hover:bg-danger-container transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
      >
        <Icon name="trash" size={17} />
      </button> : <span aria-hidden="true" className="md:order-last" />}
      <div className="text-sm">
        <p className="eyebrow">Date range</p>
        <p className="mt-1 text-on-surface tabular-nums">
          {yearOf(project.date_range_start)} – {yearOf(project.date_range_end)}
        </p>
      </div>
      <div className="text-sm">
        <p className="eyebrow">Created</p>
        <p className="mt-1 text-on-surface tabular-nums">{new Date(project.created_at).toLocaleDateString()}</p>
      </div>
    </li>
  );
}
