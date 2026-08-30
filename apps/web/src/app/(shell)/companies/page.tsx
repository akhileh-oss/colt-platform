import type { Metadata } from "next";

import { CompaniesPage } from "@/features/companies/companies-page";

export const metadata: Metadata = { title: "Companies" };

export default function Page() {
  return <CompaniesPage />;
}
