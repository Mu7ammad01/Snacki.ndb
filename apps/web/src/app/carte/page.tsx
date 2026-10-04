import type { Metadata } from "next";

import CardView from "@/components/CardView";

export const metadata: Metadata = { title: "Ma carte fidélité — Snacki", robots: { index: false, follow: false } };

/** Page ouverte par le QR de la carte : le numéro reste dans le fragment (#), jamais dans l'URL envoyée. */
export default function CartePage() {
  return <CardView />;
}
