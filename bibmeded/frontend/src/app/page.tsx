"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { projectsApi, Project } from "@/lib/api";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    projectsApi.list()
      .then((res) => setProjects(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      {/* Welcome Hero */}
      <div className="mb-12">
        <h2 className="text-4xl font-extrabold tracking-tight text-[#191c1e] mb-2" style={{fontFamily: "'Manrope', sans-serif"}}>
          Welcome to BibMedEd
        </h2>
        <p className="text-[#43474e] max-w-2xl">
          Your clinical editorial pipeline for bibliometric analysis. Search PubMed, analyze trends, and visualize research networks.
        </p>
      </div>

      {/* Summary Stats Bar */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        <div className="card-elevated p-6 flex flex-col justify-between">
          <span className="text-[10px] font-bold uppercase tracking-widest text-[#43474e]">Total Publications</span>
          <div className="flex items-baseline gap-2 mt-4">
            <span className="text-4xl font-extrabold text-[#001e4f]" style={{fontFamily: "'Manrope', sans-serif"}}>
              {loading ? "—" : projects.length > 0 ? "—" : "0"}
            </span>
            <span className="text-xs text-[#002626] font-bold">across all projects</span>
          </div>
        </div>
        <div className="card-elevated p-6 flex flex-col justify-between">
          <span className="text-[10px] font-bold uppercase tracking-widest text-[#43474e]">Active Projects</span>
          <div className="flex items-baseline gap-2 mt-4">
            <span className="text-4xl font-extrabold text-[#001e4f]" style={{fontFamily: "'Manrope', sans-serif"}}>
              {loading ? "—" : projects.length.toString().padStart(2, "0")}
            </span>
            <span className="material-symbols-outlined text-[#76d6d5]" style={{fontVariationSettings: "'FILL' 1"}}>auto_graph</span>
          </div>
        </div>
        <div className="card-elevated p-6 flex flex-col justify-between">
          <span className="text-[10px] font-bold uppercase tracking-widest text-[#43474e]">Analysis Types</span>
          <div className="flex items-baseline gap-2 mt-4">
            <span className="text-4xl font-extrabold text-[#001e4f]" style={{fontFamily: "'Manrope', sans-serif"}}>06</span>
            <div className="ml-auto flex -space-x-2">
              <div className="w-6 h-6 rounded-full bg-[#93f2f2] flex items-center justify-center border-2 border-white text-[8px] font-bold text-[#002626]">PB</div>
              <div className="w-6 h-6 rounded-full bg-[#d5e3fc] flex items-center justify-center border-2 border-white text-[8px] font-bold text-[#57657a]">AU</div>
            </div>
          </div>
        </div>
      </section>

      {/* Projects Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-[#191c1e]" style={{fontFamily: "'Manrope', sans-serif"}}>Active Projects</h3>
        <span className="text-sm font-semibold text-[#001e4f] cursor-pointer hover:underline">{projects.length} total</span>
      </div>

      {/* Projects Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-[#43474e]">
          <span className="material-symbols-outlined animate-spin mr-2">sync</span>
          Loading projects...
        </div>
      ) : (
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <Link key={project.id} href={`/projects/${project.id}/results`}>
              <article className="card-elevated p-6 group relative overflow-hidden cursor-pointer">
                <div className="absolute top-0 right-0 w-24 h-24 bg-[#002626]/5 rounded-bl-full -mr-8 -mt-8 group-hover:bg-[#002626]/10 transition-colors" />
                <div className="flex justify-between items-start mb-4">
                  <div className="px-3 py-1 bg-[#93f2f2] text-[#002626] text-[10px] font-bold uppercase tracking-widest rounded-full">
                    Bibliometric
                  </div>
                  <span className="material-symbols-outlined text-[#43474e] opacity-0 group-hover:opacity-100 transition-opacity">more_vert</span>
                </div>
                <h4 className="text-lg font-bold text-[#191c1e] mb-2" style={{fontFamily: "'Manrope', sans-serif"}}>{project.name}</h4>
                <p className="text-sm text-[#43474e] mb-6 line-clamp-2">
                  {project.description || "No description provided"}
                </p>
                <div className="flex items-center justify-between pt-4 border-t border-[#eceef0]">
                  <div>
                    <p className="text-[10px] uppercase font-bold text-[#43474e]">Date Range</p>
                    <p className="text-xs font-semibold text-[#001e4f]">
                      {project.date_range_start ? new Date(project.date_range_start).getFullYear() : "—"} – {project.date_range_end ? new Date(project.date_range_end).getFullYear() : "—"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] uppercase font-bold text-[#43474e]">Created</p>
                    <p className="text-xs font-semibold text-[#191c1e]">{new Date(project.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
              </article>
            </Link>
          ))}

          {/* New Project Card */}
          <Link href="/projects/new">
            <button className="w-full bg-[#001e4f]/5 border-2 border-dashed border-[#001e4f]/20 p-6 rounded-xl flex flex-col items-center justify-center gap-4 hover:bg-[#001e4f]/10 transition-colors group min-h-[240px]">
              <div className="w-16 h-16 rounded-full bg-[#001e4f] text-white flex items-center justify-center shadow-lg group-active:scale-95 transition-transform">
                <span className="material-symbols-outlined text-3xl">add</span>
              </div>
              <div className="text-center">
                <h4 className="text-lg font-bold text-[#001e4f]" style={{fontFamily: "'Manrope', sans-serif"}}>New Project</h4>
                <p className="text-xs font-semibold text-[#43474e]">Start a new bibliometric analysis</p>
              </div>
            </button>
          </Link>
        </section>
      )}
    </div>
  );
}
