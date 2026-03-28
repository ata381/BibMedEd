export function StatusBar() {
  return (
    <footer className="fixed bottom-0 left-0 w-full flex justify-between items-center px-6 z-50 bg-blue-950 h-8">
      <div className="flex items-center gap-6">
        <div className="text-cyan-400 flex items-center gap-2 text-[11px] uppercase tracking-widest font-medium" style={{fontFamily: "'Inter', sans-serif"}}>
          <span className="material-symbols-outlined text-sm">cloud_done</span>
          PubMed Connected
        </div>
        <div className="text-slate-400 flex items-center gap-2 text-[11px] uppercase tracking-widest font-medium" style={{fontFamily: "'Inter', sans-serif"}}>
          <span className="material-symbols-outlined text-sm">sync</span>
          Task Progress
        </div>
      </div>
      <div className="text-[10px] text-slate-500 font-medium">
        System Status: <span className="text-cyan-400">Optimal</span>
      </div>
    </footer>
  );
}
