"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { exportApi } from "@/lib/api";
import toast from "react-hot-toast";

export default function ExportManager() {
  const params = useParams<{ id: string }>();
  const projectId = Number(params.id);
  const [dataFormat, setDataFormat] = useState<"csv" | "ris">("csv");
  const [activeTab, setActiveTab] = useState<"data" | "methodology">("data");
  const [methodologyText, setMethodologyText] = useState<string | null>(null);
  const [loadingMethodology, setLoadingMethodology] = useState(false);

  const loadMethodology = async () => {
    if (methodologyText) return;
    setLoadingMethodology(true);
    try {
      const response = await fetch(exportApi.methodologyUrl(projectId));
      const text = await response.text();
      setMethodologyText(text);
    } catch {
      toast.error("Failed to load methodology log.");
    } finally {
      setLoadingMethodology(false);
    }
  };

  const handleDataExport = () => {
    const url = dataFormat === "csv" ? exportApi.csvUrl(projectId) : exportApi.risUrl(projectId);
    window.open(url, "_blank");
    toast.success(`${dataFormat.toUpperCase()} download started.`);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-12">
      {/* Header */}
      <header className="mb-12">
        <div className="flex items-baseline gap-4 mb-2">
          <h1 className="text-5xl font-extrabold text-[#001e4f] tracking-tight" style={{fontFamily:"'Manrope',sans-serif"}}>Export Manager</h1>
          <span className="h-1 w-12 bg-[#76d6d5] rounded-full" />
        </div>
        <p className="text-[#43474e] text-lg max-w-2xl leading-relaxed">
          Export your curated bibliometric data. Select from formats optimized for reference managers, spreadsheets, or supplementary submission files.
        </p>
      </header>

      {/* Tabs */}
      <div className="flex gap-2 mb-8">
        <button onClick={() => setActiveTab("data")}
          className={`px-5 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === "data" ? "bg-[#001e4f] text-white" : "bg-[#eceef0] text-[#43474e] hover:bg-[#e6e8ea]"}`}>
          Data Export
        </button>
        <button onClick={() => { setActiveTab("methodology"); loadMethodology(); }}
          className={`px-5 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === "methodology" ? "bg-[#001e4f] text-white" : "bg-[#eceef0] text-[#43474e] hover:bg-[#e6e8ea]"}`}>
          Methodology Log
        </button>
      </div>

      {activeTab === "data" && (
      <>{/* Bento Grid */}
      <div className="grid grid-cols-12 gap-8">
        {/* Raw Data Export - Primary */}
        <section className="col-span-12 lg:col-span-8 bg-white rounded-xl p-10 flex flex-col md:flex-row gap-10 items-center shadow-sm relative overflow-hidden group">
          <div className="flex-1 space-y-6 z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#001e4f]/5 text-[#001e4f] text-[10px] font-bold uppercase tracking-widest">
              <span className="material-symbols-outlined text-sm">auto_awesome</span> Recommended
            </div>
            <h2 className="text-3xl font-bold text-[#001e4f] leading-tight" style={{fontFamily:"'Manrope',sans-serif"}}>CSV Spreadsheet Export</h2>
            <p className="text-[#43474e] text-sm leading-relaxed">
              Full extraction of all publication metadata including authors, journals, citations, keywords, and abstracts in a single spreadsheet.
            </p>
            <ul className="space-y-3">
              <li className="flex items-center gap-3 text-xs font-semibold text-[#191c1e]">
                <span className="material-symbols-outlined text-[#76d6d5] scale-75" style={{fontVariationSettings:"'FILL' 1"}}>check_circle</span>
                Complete metadata (PMID, DOI, Authors, Journal, Year)
              </li>
              <li className="flex items-center gap-3 text-xs font-semibold text-[#191c1e]">
                <span className="material-symbols-outlined text-[#76d6d5] scale-75" style={{fontVariationSettings:"'FILL' 1"}}>check_circle</span>
                Citation counts and keyword annotations
              </li>
              <li className="flex items-center gap-3 text-xs font-semibold text-[#191c1e]">
                <span className="material-symbols-outlined text-[#76d6d5] scale-75" style={{fontVariationSettings:"'FILL' 1"}}>check_circle</span>
                Excel / Google Sheets compatible
              </li>
            </ul>
            <div className="pt-4">
              <a href={exportApi.csvUrl(projectId)} download
                className="inline-flex items-center gap-2 bg-[#001e4f] text-white px-8 py-3 rounded-lg font-bold text-sm hover:opacity-90 transition">
                Download CSV <span className="material-symbols-outlined text-sm">download</span>
              </a>
            </div>
          </div>
          <div className="w-full md:w-64 aspect-[3/4] bg-[#eceef0] rounded-lg flex items-center justify-center">
            <span className="material-symbols-outlined text-6xl text-[#c4c6cf]">table_chart</span>
          </div>
        </section>

        {/* RIS / Reference Manager */}
        <section className="col-span-12 lg:col-span-4 bg-[#f2f4f6] rounded-xl p-8 flex flex-col justify-between shadow-sm">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center text-[#001e4f] shadow-sm">
              <span className="material-symbols-outlined text-2xl">menu_book</span>
            </div>
            <h3 className="text-xl font-bold text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>Reference Manager</h3>
            <p className="text-xs text-[#43474e] leading-relaxed">Export in formats compatible with EndNote, Zotero, and Mendeley.</p>
            <div className="space-y-2 pt-2">
              <label className="flex items-center gap-3 p-3 bg-white rounded-lg cursor-pointer" onClick={() => setDataFormat("csv")}>
                <input type="radio" name="format" checked={dataFormat === "csv"} readOnly className="text-[#001e4f]" />
                <span className="text-sm font-semibold flex-1">CSV (Spreadsheet)</span>
              </label>
              <label className="flex items-center gap-3 p-3 bg-white/50 rounded-lg cursor-pointer hover:bg-white" onClick={() => setDataFormat("ris")}>
                <input type="radio" name="format" checked={dataFormat === "ris"} readOnly className="text-[#001e4f]" />
                <span className="text-sm font-semibold flex-1">RIS (EndNote / Zotero)</span>
              </label>
            </div>
          </div>
          <button onClick={handleDataExport}
            className="mt-8 w-full py-3 bg-[#191c1e] text-white rounded-lg font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-[#001e4f] transition">
            Download {dataFormat.toUpperCase()} <span className="material-symbols-outlined text-sm">download</span>
          </button>
        </section>

        {/* Info Banner */}
        <section className="col-span-12 bg-white rounded-xl p-8 shadow-sm border-l-4 border-[#76d6d5]">
          <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-8">
            <div className="flex-1 space-y-2">
              <h3 className="text-xl font-bold text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>About Export Formats</h3>
              <p className="text-sm text-[#43474e]">
                <strong>CSV</strong> includes all metadata in a flat table — ideal for Excel, Google Sheets, or statistical analysis.
                <strong className="ml-2">RIS</strong> is the standard interchange format for reference managers (EndNote, Zotero, Mendeley).
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-4 bg-[#f2f4f6] p-3 rounded-lg min-w-[180px]">
                <span className="material-symbols-outlined text-[#002626]">table_chart</span>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-tighter opacity-60">CSV</p>
                  <p className="text-sm font-bold">Spreadsheet</p>
                </div>
                <a href={exportApi.csvUrl(projectId)} download className="ml-auto p-2 hover:bg-[#e6e8ea] rounded-full transition-colors">
                  <span className="material-symbols-outlined text-lg">download</span>
                </a>
              </div>
              <div className="flex items-center gap-4 bg-[#f2f4f6] p-3 rounded-lg min-w-[180px]">
                <span className="material-symbols-outlined text-[#002626]">menu_book</span>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-tighter opacity-60">RIS</p>
                  <p className="text-sm font-bold">References</p>
                </div>
                <a href={exportApi.risUrl(projectId)} download className="ml-auto p-2 hover:bg-[#e6e8ea] rounded-full transition-colors">
                  <span className="material-symbols-outlined text-lg">download</span>
                </a>
              </div>
            </div>
          </div>
        </section>
      </div>
      </>)}

      {activeTab === "methodology" && (
        <div className="bg-white rounded-xl p-10 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-[#001e4f]" style={{fontFamily:"'Manrope',sans-serif"}}>Methodology Log</h2>
            <a href={exportApi.methodologyUrl(projectId)} download
              className="inline-flex items-center gap-2 bg-[#001e4f] text-white px-6 py-2.5 rounded-lg font-bold text-sm hover:opacity-90 transition">
              Download .txt <span className="material-symbols-outlined text-sm">download</span>
            </a>
          </div>
          <p className="text-sm text-[#43474e] mb-6">
            A complete record of every pipeline step — citable in your paper&apos;s Methods section.
          </p>
          {loadingMethodology ? (
            <div className="text-center py-12 text-[#43474e]">
              <span className="material-symbols-outlined animate-spin text-2xl">sync</span>
              <p className="mt-2 text-sm">Loading methodology log...</p>
            </div>
          ) : methodologyText ? (
            <pre className="bg-[#0a1628] text-[#93f2f2] font-mono text-xs rounded-lg p-6 overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {methodologyText}
            </pre>
          ) : (
            <p className="text-sm text-[#43474e]">No methodology data available yet. Run a search first.</p>
          )}
        </div>
      )}
    </div>
  );
}
