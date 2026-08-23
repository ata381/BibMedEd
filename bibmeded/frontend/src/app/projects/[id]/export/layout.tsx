import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Export project",
};

export default function ExportLayout({ children }: { children: React.ReactNode }) {
  return children;
}
