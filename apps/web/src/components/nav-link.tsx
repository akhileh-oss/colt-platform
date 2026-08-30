"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface NavLinkProps {
  href: string;
  label: string;
  /**
   * A pre-rendered icon element, not a component reference: a raw component type crossing from
   * a Server Component into this Client Component fails RSC serialization (functions are not
   * serializable), whereas an already-rendered element is (CLAUDE.md §78 aside — this is a
   * framework constraint, not a design one).
   */
  icon: ReactNode;
}

export function NavLink({ href, label, icon }: NavLinkProps) {
  const pathname = usePathname();
  const isActive = pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      aria-current={isActive ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        isActive
          ? "bg-secondary text-secondary-foreground"
          : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
      )}
    >
      {icon}
      {label}
    </Link>
  );
}
