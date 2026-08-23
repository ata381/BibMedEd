import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analysis dashboard",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
