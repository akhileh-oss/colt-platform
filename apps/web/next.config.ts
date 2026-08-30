import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Never mask a type failure to get a green build (CLAUDE.md §0.4). Lint runs as its own
  // `make lint` / `pnpm lint` step, covering the whole workspace with one shared config,
  // rather than through a Next-specific build-time toggle.
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
