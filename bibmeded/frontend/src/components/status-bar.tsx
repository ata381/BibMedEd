export function StatusBar() {
  return (
    <footer aria-label="Application status" className="fixed bottom-0 left-0 w-full flex justify-between items-center gap-4 px-4 sm:px-6 z-50 bg-blue-950 min-h-8 py-1">
      <div className="flex items-center gap-4 sm:gap-6 min-w-0">
        <div className="text-cyan-300 flex items-center gap-2 text-[11px] uppercase tracking-wider font-semibold" style={{fontFamily: "'Inter', sans-serif"}}>
          <span aria-hidden="true" className="material-symbols-outlined text-sm">storage</span>
          <span className="hidden sm:inline">Local workspace</span>
        </div>
        <div className="text-slate-300 flex items-center gap-2 text-[11px] uppercase tracking-wider font-semibold" style={{fontFamily: "'Inter', sans-serif"}}>
          <span aria-hidden="true" className="material-symbols-outlined text-sm">hub</span>
          <span className="hidden sm:inline">5 sources available</span>
        </div>
      </div>
      <div className="text-[11px] text-slate-300 font-semibold whitespace-nowrap">
        Status: <span className="text-cyan-300">Ready</span>
      </div>
    </footer>
  );
}
