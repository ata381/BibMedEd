"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "bibmeded:theme";

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.remove("light", "dark");
  if (theme === "system") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.classList.add(prefersDark ? "dark" : "light");
    root.dataset.themeChoice = "system";
  } else {
    root.classList.add(theme);
    root.dataset.themeChoice = theme;
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system";
    setTheme(stored);
    applyTheme(stored);

    if (stored !== "system") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  const change = (next: Theme) => {
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  };

  const next: Theme = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
  const icon = theme === "light" ? "light_mode" : theme === "dark" ? "dark_mode" : "contrast";
  const label = `Theme: ${theme} — click to switch to ${next}`;

  return (
    <button
      type="button"
      onClick={() => change(next)}
      aria-label={label}
      title={label}
      className={[
        "inline-flex items-center justify-center w-10 h-10 rounded-[var(--radius-md)]",
        "text-on-surface-muted hover:text-on-surface hover:bg-surface-hover",
        "cursor-pointer transition-colors duration-[var(--duration-fast)]",
        "focus-visible:outline-2 focus-visible:outline-[color:var(--color-focus-ring)] focus-visible:outline-offset-2",
      ].join(" ")}
    >
      <span className="material-symbols-outlined" aria-hidden="true">{icon}</span>
    </button>
  );
}
