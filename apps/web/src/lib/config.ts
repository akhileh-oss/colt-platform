/**
 * Browser-safe runtime configuration.
 *
 * Only `NEXT_PUBLIC_*` variables reach client components (Next.js inlines them at build time);
 * everything else stays server-only. This file is the single place that reads them, mirroring
 * the backend rule against scattering `os.getenv` (CLAUDE.md §7) for the frontend.
 */

function requireEnv(name: string, fallback: string): string {
  return process.env[name] ?? fallback;
}

export const config = {
  apiBaseUrl: requireEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000"),
} as const;
