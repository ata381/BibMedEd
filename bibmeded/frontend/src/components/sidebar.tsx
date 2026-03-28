"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", icon: "folder_open", label: "Projects" },
];

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <aside className="fixed left-0 top-0 h-full z-40 flex flex-col p-4 bg-slate-50 w-64 border-r-0">
      <div className="mb-10 px-4">
        <h1 className="text-xl font-extrabold tracking-tighter text-blue-950" style={{fontFamily: "'Manrope', sans-serif"}}>BibMedEd</h1>
        <p className="text-[10px] uppercase tracking-widest text-slate-400 font-bold mt-1">Clinical Editorial</p>
      </div>

      <nav className="flex-1 flex flex-col gap-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-colors ${
              isActive(item.href)
                ? "bg-white text-blue-900 shadow-sm font-semibold"
                : "text-slate-500 hover:bg-slate-100 font-bold"
            }`}
            style={{fontFamily: "'Manrope', sans-serif"}}
          >
            <span className="material-symbols-outlined">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="mt-auto p-4 bg-[#f2f4f6] rounded-xl">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[#00327a] flex items-center justify-center text-[#739cfb] font-bold text-xs">
            U
          </div>
          <div>
            <p className="text-xs font-bold text-[#191c1e]">Researcher</p>
            <p className="text-[10px] text-[#43474e]">Medical Education</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
