import type { LucideIcon } from "lucide-react";
import {
  Bot,
  Building2,
  LayoutDashboard,
  MessageSquare,
  Settings,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

/**
 * Primary navigation (CLAUDE.md §43): one entry per feature area under `src/features/`.
 * Order follows the product loop roughly: who we're targeting, how we're reaching them, what
 * came back.
 */
export const NAV_ITEMS: readonly NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Leads", href: "/leads", icon: Users },
  { label: "Companies", href: "/companies", icon: Building2 },
  { label: "Campaigns", href: "/campaigns", icon: Target },
  { label: "Conversations", href: "/conversations", icon: MessageSquare },
  { label: "Opportunities", href: "/opportunities", icon: TrendingUp },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Settings", href: "/settings", icon: Settings },
] as const;
