import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "New project",
};

export default function NewProjectLayout({ children }: { children: React.ReactNode }) {
  return children;
}
