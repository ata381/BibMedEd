import type { Metadata } from "next";
import localFont from "next/font/local";
import Script from "next/script";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { StatusBar } from "@/components/status-bar";
import { ToastProvider } from "@/components/toast-provider";

const crimson = localFont({
  src: [
    { path: "./fonts/crimson-pro/CrimsonPro-latin.woff2", weight: "200 900", style: "normal" },
    { path: "./fonts/crimson-pro/CrimsonPro-Italic-latin.woff2", weight: "200 900", style: "italic" },
  ],
  variable: "--font-crimson",
  display: "swap",
});

const atkinson = localFont({
  src: [
    { path: "./fonts/atkinson-hyperlegible-next/AtkinsonHyperlegibleNext-latin.woff2", weight: "200 800", style: "normal" },
    { path: "./fonts/atkinson-hyperlegible-next/AtkinsonHyperlegibleNext-Italic-latin.woff2", weight: "200 800", style: "italic" },
  ],
  variable: "--font-atkinson",
  display: "swap",
  adjustFontFallback: false,
  fallback: ["system-ui", "Segoe UI", "Helvetica Neue", "sans-serif"],
});

export const metadata: Metadata = {
  title: {
    default: "BibMedEd — Bibliometric Analysis for Medical Education",
    template: "%s | BibMedEd",
  },
  description:
    "Search PubMed, OpenAlex, CrossRef, Semantic Scholar, and Lens.org. Analyze trends. Visualize co-authorship and keyword networks. Export PRISMA-ready methodology logs.",
};

// No-flash theme bootstrap: runs before React hydration so the first paint
// already uses the user's stored / system preference.
const THEME_BOOTSTRAP = `
(function() {
  try {
    var stored = localStorage.getItem('bibmeded:theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var theme = stored || 'system';
    var resolved = theme === 'system' ? (prefersDark ? 'dark' : 'light') : theme;
    document.documentElement.classList.add(resolved);
    document.documentElement.dataset.themeChoice = theme;
  } catch (e) {
    document.documentElement.classList.add('light');
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script id="theme-bootstrap" strategy="beforeInteractive">
          {THEME_BOOTSTRAP}
        </Script>
      </head>
      <body
        suppressHydrationWarning
        className={`${crimson.variable} ${atkinson.variable} font-sans antialiased paper text-on-surface min-h-screen flex`}
      >
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-16 md:focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-ink focus:text-on-ink focus:rounded-[var(--radius-md)]"
        >
          Skip to main content
        </a>
        <Sidebar />
        <div className="flex-1 min-w-0 md:ml-[17rem] min-h-screen flex flex-col">
          <main id="main" className="px-4 pt-20 pb-12 md:px-10 md:pt-10 lg:px-14 max-w-7xl w-full mx-auto flex-1">
            {children}
          </main>
          <StatusBar />
        </div>
        <ToastProvider />
      </body>
    </html>
  );
}
