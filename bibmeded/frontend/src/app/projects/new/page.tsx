"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { projectsApi } from "@/lib/api";
import toast from "react-hot-toast";

export default function NewProject() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dateStart, setDateStart] = useState("2022-01-01");
  const [dateEnd, setDateEnd] = useState("2025-06-30");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    if (dateStart && dateEnd && dateStart > dateEnd) {
      toast.error("Start date must be before end date.");
      return;
    }
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
    <div className="max-w-xl mx-auto pt-8">
      <h1 className="font-serif text-3xl mb-2">New Project</h1>
      <p className="text-slate-500 mb-8">Set up your bibliometric analysis project.</p>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-xs uppercase tracking-wider text-slate-500 mb-2">Project Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., AI in Medical Education Curriculum"
            className="w-full bg-[#eceef0] rounded-lg px-4 py-3 text-[#191c1e] placeholder-slate-400 focus:outline-none focus:border-[#2b5bb5] focus:bg-[#f2f4f6] border-b-2 border-transparent transition"
            required
          />
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-slate-500 mb-2">Description <span className="text-slate-600">(optional)</span></label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Brief description of your analysis..."
            rows={3}
            className="w-full bg-[#eceef0] rounded-lg px-4 py-3 text-[#191c1e] placeholder-slate-400 focus:outline-none focus:border-[#2b5bb5] focus:bg-[#f2f4f6] border-b-2 border-transparent transition-all resize-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-2">Date Range Start</label>
            <input
              type="date"
              value={dateStart}
              onChange={(e) => setDateStart(e.target.value)}
              className="w-full bg-[#eceef0] rounded-lg px-4 py-3 text-[#191c1e] focus:outline-none focus:border-[#2b5bb5] focus:bg-[#f2f4f6] border-b-2 border-transparent transition-all"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-2">Date Range End</label>
            <input
              type="date"
              value={dateEnd}
              onChange={(e) => setDateEnd(e.target.value)}
              className="w-full bg-[#eceef0] rounded-lg px-4 py-3 text-[#191c1e] focus:outline-none focus:border-[#2b5bb5] focus:bg-[#f2f4f6] border-b-2 border-transparent transition-all"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || !name.trim()}
          className="w-full bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-black font-medium py-3 rounded-lg transition-all hover:shadow-lg hover:shadow-amber-500/20"
        >
          {loading ? "Creating..." : "Continue to Search →"}
        </button>
      </form>
    </div>
  );
}
