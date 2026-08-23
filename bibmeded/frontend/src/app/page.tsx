"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { projectsApi, Project } from "@/lib/api";
import toast from "react-hot-toast";
import { Badge, Button, Card, EmptyState, Skeleton } from "@/components/ui";

export default function Home() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingSample, setCreatingSample] = useState(false);

  useEffect(() => {
    projectsApi.list()
      .then((res) => setProjects(res.data))
      .catch(() => toast.error("Failed to load projects. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = (project: Project) => {
    if (!confirm(`Delete project "${project.name}"? This will permanently remove all searches, publications, and analyses.`)) return;
    projectsApi.delete(project.id)
      .then(() => { setProjects((prev) => prev.filter((p) => p.id !== project.id)); toast.success("Project deleted"); })
      .catch(() => toast.error("Failed to delete project"));
  };

  const handleCreateSample = async () => {
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

  return (
    <div className="py-10 space-y-10">
      <header className="space-y-3">
        <Badge tone="primary">Workspace</Badge>
        <h1
          className="text-4xl md:text-5xl font-extrabold tracking-tight text-primary"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Welcome to BibMedEd
        </h1>
        <p className="text-on-surface-muted text-base md:text-lg max-w-2xl leading-relaxed">
          Search PubMed, OpenAlex, CrossRef, Semantic Scholar, and Lens.org; deduplicate across sources; run six bibliometric analyses; export a PRISMA-ready methodology log.
        </p>
      </header>

      <section aria-label="Workspace summary" className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard label="Active projects" value={loading ? null : projects.length.toString().padStart(2, "0")} icon="folder_open" />
        <StatCard label="Data sources" value="05" icon="hub" subtitle="PubMed · OpenAlex · CrossRef · Semantic Scholar · Lens.org" />
        <StatCard label="Analysis modules" value="06" icon="auto_graph" subtitle="Publications · Authors · Keywords · …" />
      </section>

      <section>
        <div className="flex items-baseline justify-between mb-5">
          <h2
            className="text-xl font-bold text-on-surface"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Projects
          </h2>
          <span className="text-sm text-on-surface-muted tabular-nums">
            {loading ? "—" : `${projects.length} total`}
          </span>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} rounded="lg" className="h-[240px]" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <Card padding="lg">
            <EmptyState
              icon="folder_off"
              title="No projects yet"
              description="Start a bibliometric analysis by creating your first project."
              action={
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Link href="/projects/new">
                    <Button leadingIcon="add" size="lg">New project</Button>
                  </Link>
                  <Button
                    leadingIcon="science"
                    size="lg"
                    onClick={handleCreateSample}
                    loading={creatingSample}
                    disabled={creatingSample}
                  >
                    {creatingSample ? "Building sample project..." : "Explore sample project"}
                  </Button>
                </div>
              }
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} onDelete={handleDelete} />
            ))}
            <Link
              href="/projects/new"
              className="group flex flex-col items-center justify-center gap-4 min-h-[240px] rounded-[var(--radius-lg)] border-2 border-dashed border-outline hover:border-primary hover:bg-primary-container/30 transition-colors focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
            >
              <span
                aria-hidden="true"
                className="w-14 h-14 rounded-full bg-primary text-on-primary flex items-center justify-center elev-2 group-active:scale-95 transition-transform"
              >
                <span className="material-symbols-outlined" style={{ fontSize: "28px" }}>add</span>
              </span>
              <span className="text-center">
                <span
                  className="block text-lg font-bold text-primary"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  New project
                </span>
                <span className="block text-xs text-on-surface-muted mt-1">
                  Start a new bibliometric analysis
                </span>
              </span>
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, icon, subtitle }: { label: string; value: string | null; icon: string; subtitle?: string }) {
  return (
    <Card padding="md">
      <div className="flex items-start justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-on-surface-subtle">{label}</span>
        <span
          aria-hidden="true"
          className="material-symbols-outlined text-secondary"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          {icon}
        </span>
      </div>
      <p
        className="mt-3 text-4xl font-extrabold text-primary tabular-nums"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {value ?? "—"}
      </p>
      {subtitle ? <p className="mt-1 text-xs text-on-surface-muted">{subtitle}</p> : null}
    </Card>
  );
}

function ProjectCard({ project, onDelete }: { project: Project; onDelete: (p: Project) => void }) {
  return (
    <Card padding="md" interactive className="relative group">
      <Link
        href={`/projects/${project.id}/results`}
        aria-label={`Open project ${project.name}`}
        className="absolute inset-0 rounded-[var(--radius-lg)] focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
      />
      <div className="relative flex justify-between items-start mb-4">
        <Badge tone="info">Bibliometric</Badge>
        <button
          type="button"
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(project); }}
          aria-label={`Delete project ${project.name}`}
          className="relative z-10 p-1.5 rounded-[var(--radius-sm)] text-on-surface-muted hover:text-danger hover:bg-danger-container transition-colors focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2"
        >
          <span className="material-symbols-outlined" aria-hidden="true">delete</span>
        </button>
      </div>
      <h3
        className="relative text-lg font-bold text-on-surface mb-2 line-clamp-2"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {project.name}
      </h3>
      <p className="relative text-sm text-on-surface-muted mb-5 line-clamp-2 leading-relaxed">
        {project.description || "No description provided"}
      </p>
      <div className="relative flex items-center justify-between pt-4 border-t border-divider">
        <div>
          <p className="text-[10px] uppercase font-bold tracking-[0.14em] text-on-surface-subtle">Date range</p>
          <p className="text-xs font-semibold text-primary tabular-nums">
            {project.date_range_start ? new Date(project.date_range_start).getFullYear() : "—"} – {project.date_range_end ? new Date(project.date_range_end).getFullYear() : "—"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase font-bold tracking-[0.14em] text-on-surface-subtle">Created</p>
          <p className="text-xs font-semibold text-on-surface tabular-nums">{new Date(project.created_at).toLocaleDateString()}</p>
        </div>
      </div>
    </Card>
  );
}
