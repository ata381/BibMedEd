"use client";

import { useParams } from "next/navigation";

export default function ExportManager() {
  const params = useParams<{ id: string }>();

  return (
    <div className="max-w-7xl mx-auto px-4 py-12">
      {/* Header */}
      <header className="mb-12">
        <div className="flex items-baseline gap-4 mb-2">
          <h1 className="text-5xl font-extrabold text-[#001e4f] tracking-tight" style={{fontFamily:"'Manrope',sans-serif"}}>Export Manager</h1>
          <span className="h-1 w-12 bg-[#76d6d5] rounded-full" />
        </div>
        <p className="text-[#43474e] text-lg max-w-2xl leading-relaxed">
          Review and distribute your curated clinical insights. Select from precision formats optimized for publication, raw analysis, or stakeholder presentations.
        </p>
      </header>

      {/* Bento Grid */}
      <div className="grid grid-cols-12 gap-8">
        {/* PDF Report */}
        <section className="col-span-12 lg:col-span-8 bg-white rounded-xl p-10 flex flex-col md:flex-row gap-10 items-center shadow-sm relative overflow-hidden group">
          <div className="flex-1 space-y-6 z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#001e4f]/5 text-[#001e4f] text-[10px] font-bold uppercase tracking-widest">
              <span className="material-symbols-outlined text-sm">auto_awesome</span> Recommended
            </div>
            <h2 className="text-3xl font-bold text-[#001e4f] leading-tight" style={{fontFamily:"'Manrope',sans-serif"}}>Comprehensive PDF Research Report</h2>
            <p className="text-[#43474e] text-sm leading-relaxed">
              Full-length editorial compilation including bibliometric heatmaps, abstract summaries, and methodology disclosure.
            </p>
            <ul className="space-y-3">
              <li className="flex items-center gap-3 text-xs font-semibold text-[#191c1e]">
                <span className="material-symbols-outlined text-[#76d6d5] scale-75" style={{fontVariationSettings:"'FILL' 1"}}>check_circle</span>
                Dynamic Citations Index
              </li>
              <li className="flex items-center gap-3 text-xs font-semibold text-[#191c1e]">
                <span className="material-symbols-outlined text-[#76d6d5] scale-75" style={{fontVariationSettings:"'FILL' 1"}}>check_circle</span>
                Network Analysis Overlays
              </li>
            </ul>
            <div className="pt-4 flex gap-4">
              <button className="bg-[#001e4f] text-white px-8 py-3 rounded-lg font-bold text-sm flex items-center gap-2 hover:opacity-90 transition">
                Download PDF <span className="material-symbols-outlined text-sm">download</span>
              </button>
              <button className="text-[#001e4f] font-bold text-sm hover:underline">Preview</button>
            </div>
          </div>
          <div className="w-full md:w-64 aspect-[3/4] bg-[#e6e8ea] rounded-lg flex items-center justify-center">
            <span className="material-symbols-outlined text-6xl text-[#c4c6cf]">picture_as_pdf</span>
          </div>
        </section>

        {/* Raw Data */}
        <section className="col-span-12 lg:col-span-4 bg-[#f2f4f6] rounded-xl p-8 flex flex-col justify-between shadow-sm">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center text-[#001e4f] shadow-sm">
              <span className="material-symbols-outlined text-2xl">table_chart</span>
            </div>
            <h3 className="text-xl font-bold text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>Raw Data Export</h3>
            <p className="text-xs text-[#43474e] leading-relaxed">Full extraction of metadata in tabular formats.</p>
            <div className="space-y-2 pt-2">
              <label className="flex items-center gap-3 p-3 bg-white rounded-lg cursor-pointer">
                <input type="radio" name="format" defaultChecked className="text-[#001e4f]" />
                <span className="text-sm font-semibold flex-1">CSV (Spreadsheet)</span>
              </label>
              <label className="flex items-center gap-3 p-3 bg-white/50 rounded-lg cursor-pointer hover:bg-white">
                <input type="radio" name="format" className="text-[#001e4f]" />
                <span className="text-sm font-semibold flex-1">Excel (XLSX)</span>
              </label>
            </div>
          </div>
          <button className="mt-8 w-full py-3 bg-[#191c1e] text-white rounded-lg font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-[#001e4f] transition">
            Generate Data <span className="material-symbols-outlined text-sm">arrow_forward</span>
          </button>
        </section>

        {/* Visual Assets */}
        <section className="col-span-12 bg-white rounded-xl p-8 shadow-sm border-l-4 border-[#76d6d5]">
          <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-8">
            <div className="flex-1 space-y-2">
              <h3 className="text-xl font-bold text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>High-Resolution Visualizations</h3>
              <p className="text-sm text-[#43474e]">Export citation networks and keyword heatmaps as vector or raster assets.</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-4 bg-[#f2f4f6] p-3 rounded-lg min-w-[180px]">
                <span className="material-symbols-outlined text-[#002626]">image</span>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-tighter opacity-60">PNG Raster</p>
                  <p className="text-sm font-bold">300 DPI</p>
                </div>
                <button className="ml-auto p-2 hover:bg-[#e6e8ea] rounded-full transition-colors">
                  <span className="material-symbols-outlined text-lg">download</span>
                </button>
              </div>
              <div className="flex items-center gap-4 bg-[#f2f4f6] p-3 rounded-lg min-w-[180px]">
                <span className="material-symbols-outlined text-[#002626]">slide_library</span>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-tighter opacity-60">SVG Vector</p>
                  <p className="text-sm font-bold">Scalable</p>
                </div>
                <button className="ml-auto p-2 hover:bg-[#e6e8ea] rounded-full transition-colors">
                  <span className="material-symbols-outlined text-lg">download</span>
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
