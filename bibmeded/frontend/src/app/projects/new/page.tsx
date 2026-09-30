"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { projectsApi } from "@/lib/api";
import { useReadOnly } from "@/lib/read-only";
import { WORKFLOW_STEPS } from "@/lib/sources";
import { Button, Card, PageHeader } from "@/components/ui";

export default function NewProject() {
  const router = useRouter();
  const readOnly = useReadOnly();
  useEffect(() => {
    if (readOnly) router.replace("/");
  }, [readOnly, router]);
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
    <div className="space-y-10">
      <PageHeader
        eyebrow="Step 1 · Setup"
        title="New project"
        lede="Name the review and set its publication window. Sources and search terms come next, and every choice is written to the methodology log."
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        <Card padding="lg" as="section" aria-labelledby="project-form-heading" className="lg:col-span-7">
          <h2 id="project-form-heading" className="sr-only">
            Project details
          </h2>
          <form onSubmit={handleSubmit} className="space-y-6">
            <Field label="Project name" htmlFor="name" required>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., AI in Medical Education Curriculum"
                required
                className="field"
                autoFocus
              />
            </Field>

            <Field label="Description" htmlFor="description" hint="One or two sentences for your records — shown in the project list.">
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of your analysis…"
                rows={3}
                className="field resize-none"
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
                  className="field"
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
                  className="field"
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
                trailingIcon={loading ? undefined : "arrowRight"}
                disabled={!name.trim() || readOnly !== false}
              >
                {loading ? "Creating project…" : "Continue to search"}
              </Button>
            </div>
          </form>
        </Card>

        <aside className="lg:col-span-5 lg:pl-4" aria-labelledby="next-steps-heading">
          <h2 id="next-steps-heading" className="eyebrow mb-4">
            What happens next
          </h2>
          <ol className="rule-t">
            {WORKFLOW_STEPS.map((step, i) => (
              <li key={step.suffix} className="flex gap-4 py-4 rule-b">
                <span className="numeral text-2xl text-primary leading-none w-8">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <p className="font-semibold text-on-surface">{step.label}</p>
                  <p className="mt-0.5 text-sm text-on-surface-muted">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-5 text-sm text-on-surface-subtle leading-relaxed">
            Nothing leaves this machine except the queries you send to the databases you choose.
          </p>
        </aside>
      </div>
    </div>
  );
}

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
      <label htmlFor={htmlFor} className="block text-sm font-semibold text-on-surface mb-2">
        {label}
        {required ? (
          <span className="text-danger ml-1" aria-hidden="true">
            *
          </span>
        ) : (
          <span className="text-on-surface-subtle ml-1.5 font-normal">(optional)</span>
        )}
      </label>
      {children}
      {hint ? <p className="mt-1.5 text-xs text-on-surface-subtle">{hint}</p> : null}
    </div>
  );
}
