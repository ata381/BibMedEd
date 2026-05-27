import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { StatusBar } from "@/components/status-bar";
import { ToastProvider } from "@/components/toast-provider";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope", display: "swap" });

export const metadata: Metadata = {
  title: "BibMedEd — Bibliometric Analysis for Medical Education",
  description:
    "Search PubMed, OpenAlex, and CrossRef. Analyze trends. Visualize co-authorship and keyword networks. Export PRISMA-ready methodology logs.",
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
        {/* Material Symbols Outlined isn't available via next/font/google
           (it's an icon font with variable-axes). Loading via a <link> is
           the supported path; the no-page-custom-font rule doesn't fit. */}
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
        <Script id="theme-bootstrap" strategy="beforeInteractive">
          {THEME_BOOTSTRAP}
        </Script>
      </head>
      <body
        suppressHydrationWarning
        className={`${inter.variable} ${manrope.variable} font-sans antialiased bg-surface text-on-surface min-h-screen flex`}
      >
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-on-primary focus:rounded-[var(--radius-md)]"
        >
          Skip to main content
        </a>
        <Sidebar />
        <div className="flex-1 md:ml-64 min-h-screen flex flex-col pb-8">
          <main id="main" className="px-4 pt-20 md:px-8 md:pt-8 max-w-7xl w-full mx-auto flex-1">
            {children}
          </main>
        </div>
        <StatusBar />
        <ToastProvider />
      </body>
    </html>
  );
}
