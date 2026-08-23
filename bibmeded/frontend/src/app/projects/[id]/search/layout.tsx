import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Search strategy",
};

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
