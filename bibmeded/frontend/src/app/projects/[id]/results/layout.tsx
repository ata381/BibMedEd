import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Results review",
};

export default function ResultsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
