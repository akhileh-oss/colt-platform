import type { Metadata } from "next";

import { AgentControlCenterPage } from "@/features/agents/agents-page";

export const metadata: Metadata = { title: "Agent control center" };

export default function Page() {
  return <AgentControlCenterPage />;
}
