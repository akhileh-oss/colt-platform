import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "./providers";

import "@/styles/globals.css";

export const metadata: Metadata = {
  title: {
    default: "Colt",
    template: "%s · Colt",
  },
  description: "Colt — AI Revenue Operating System",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
