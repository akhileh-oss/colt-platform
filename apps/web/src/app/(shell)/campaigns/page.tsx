import type { Metadata } from "next";

import { CampaignsPage } from "@/features/campaigns/campaigns-page";

export const metadata: Metadata = { title: "Campaigns" };

export default function Page() {
  return <CampaignsPage />;
}
