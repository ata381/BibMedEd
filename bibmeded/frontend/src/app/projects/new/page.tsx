"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { projectsApi } from "@/lib/api";
import toast from "react-hot-toast";
import { Badge, Button, Card } from "@/components/ui";

export default function NewProject() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dateStart, setDateStart] = useState("2022-01-01");
  const [dateEnd, setDateEnd] = useState("2025-06-30");
  const [dateError, setDateError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    if (dateStart && dateEnd && dateStart > dateEnd) {
      setDateError("Start date must be before end date.");
      return;
    }
    setDateError(null);
    setLoading(true);
    try {
      const res = await projectsApi.create({
        name,
        description: description || undefined,
        date_range_start: dateStart,
        date_range_end: dateEnd,
      });
      router.push(`/projects/${res.data.id}/search`);
    } catch {
      toast.error("Failed to create project. Is the backend running?");
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-10 space-y-8">
      <header className="space-y-3">
        <Badge tone="primary">Step 1 · Setup</Badge>
        <h1
          className="text-4xl md:text-5xl font-extrabold tracking-tight text-primary"
          style={{ fontFamily: "var(--font-display)" }}
        >
          New project
        </h1>
        <p className="text-on-surface-muted text-base leading-relaxed">
          Set up your bibliometric analysis. You can refine sources and search terms in the next step.
        </p>
      </header>

      <Card padding="lg" as="section">
        <form onSubmit={handleSubmit} className="space-y-6">
          <Field label="Project name" htmlFor="name" required>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., AI in Medical Education Curriculum"
              required
              className={inputClass}
              autoFocus
            />
          </Field>

          <Field
            label="Description"
            htmlFor="description"
            hint="One or two sentences for your records — shows on the project card."
          >
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of your analysis…"
              rows={3}
              className={`${inputClass} resize-none`}
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <Field label="Date range start" htmlFor="date-start">
              <input
                id="date-start"
                type="date"
                value={dateStart}
                onChange={(e) => {
                  setDateStart(e.target.value);
                  setDateError(null);
                }}
                aria-invalid={dateError ? "true" : undefined}
                aria-describedby={dateError ? "date-range-error" : undefined}
                className={inputClass}
              />
            </Field>
            <Field label="Date range end" htmlFor="date-end">
              <input
                id="date-end"
                type="date"
                value={dateEnd}
                onChange={(e) => {
                  setDateEnd(e.target.value);
                  setDateError(null);
                }}
                aria-invalid={dateError ? "true" : undefined}
                aria-describedby={dateError ? "date-range-error" : undefined}
                className={inputClass}
              />
            </Field>
          </div>

          {dateError ? (
            <p id="date-range-error" role="alert" className="-mt-2 text-sm font-semibold text-danger">
              {dateError}
            </p>
          ) : null}

          <div className="pt-2">
            <Button
              type="submit"
              size="lg"
              fullWidth
              loading={loading}
              trailingIcon={loading ? undefined : "arrow_forward"}
              disabled={!name.trim()}
            >
              {loading ? "Creating project…" : "Continue to search"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

const inputClass = [
  "w-full bg-surface rounded-[var(--radius-md)] px-4 py-3 text-on-surface",
  "border border-divider placeholder:text-on-surface-subtle",
  "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
  "focus:border-primary focus:bg-surface-raised focus:outline-2 focus:outline-[color:var(--color-focus-ring)] focus:outline-offset-2",
].join(" ");

function Field({
  label,
  htmlFor,
  hint,
  required = false,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="block text-xs uppercase tracking-[0.14em] font-bold text-on-surface-muted mb-2"
      >
        {label}
        {required ? <span className="text-danger ml-1" aria-hidden="true">*</span> : null}
        {!required ? <span className="text-on-surface-subtle ml-1 normal-case font-normal tracking-normal">(optional)</span> : null}
      </label>
      {children}
      {hint ? <p className="mt-1.5 text-xs text-on-surface-subtle">{hint}</p> : null}
    </div>
  );
}
