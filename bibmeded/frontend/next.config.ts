import type { NextConfig } from "next";

const demoPath = process.env.NEXT_PUBLIC_PAGES_DEMO_PATH;
const nextConfig: NextConfig = demoPath
  ? { output: "export", basePath: demoPath, trailingSlash: true }
  : {};

export default nextConfig;
