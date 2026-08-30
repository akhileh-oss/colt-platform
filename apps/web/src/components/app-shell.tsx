import type { ReactNode } from "react";

import { NAV_ITEMS } from "./nav-config";
import { NavLink } from "./nav-link";
import { SystemHealthBadge } from "./system-health-badge";

/**
 * The persistent operator-console shell (CLAUDE.md §43): a sidebar of feature areas, a header
 * carrying live system health, and the routed page content.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>

      <aside className="hidden w-64 shrink-0 border-r border-border bg-card md:flex md:flex-col">
        <div className="flex h-14 items-center border-b border-border px-4">
          <span className="text-sm font-semibold tracking-tight">Colt</span>
        </div>
        <nav aria-label="Primary" className="flex-1 space-y-1 p-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              label={item.label}
              icon={<item.icon aria-hidden="true" className="h-4 w-4 shrink-0" />}
            />
          ))}
        </nav>
        <div className="border-t border-border p-3">
          <SystemHealthBadge />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-border px-6">
          <span className="text-sm text-muted-foreground">Revenue operating system</span>
          <span className="md:hidden">
            <SystemHealthBadge />
          </span>
        </header>
        <main id="main-content" className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
