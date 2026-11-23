export function generateStaticParams() {
  return process.env.NEXT_PUBLIC_PAGES_DEMO_PATH ? [{ id: "1" }] : [];
}

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  return children;
}
