import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { StatusBar } from "@/components/status-bar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

export const metadata: Metadata = {
  title: "BibMedEd — Bibliometric Analysis for Medical Education",
  description: "Search PubMed. Analyze trends. Visualize networks.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="light">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
      </head>
      <body className={`${inter.variable} ${manrope.variable} font-sans antialiased bg-[#f7f9fb] text-[#191c1e] min-h-screen flex`} style={{fontFamily: "'Inter', sans-serif"}}>
        <Sidebar />
        <div className="flex-1 ml-64 min-h-screen flex flex-col pb-8">
          <main className="px-8 pt-8 max-w-7xl w-full mx-auto flex-1">
            {children}
          </main>
        </div>
        <StatusBar />
      </body>
    </html>
  );
}
