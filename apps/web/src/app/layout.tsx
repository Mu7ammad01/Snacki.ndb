import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import SwRegister from "@/components/SwRegister";

import "./globals.css";

export const dynamic = "force-dynamic"; // une CSP avec nonce exige un rendu à chaque requête

export const metadata: Metadata = {
  title: "Snacki — Jus & délices, Nouadhibou",
  description:
    "Commandez vos jus frais, salades de fruits et crêpes Snacki à Nouadhibou, à emporter ou en livraison.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icons/favicon-32.png", apple: "/icons/apple-touch-icon.png" },
  appleWebApp: { capable: true, title: "Snacki" },
};

export const viewport: Viewport = { themeColor: "#FFC400", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr" dir="ltr">
      <body>
        {children}
        <SwRegister />
      </body>
    </html>
  );
}
