import type { Metadata } from "next";

import TrackView from "@/components/TrackView";

export const metadata: Metadata = { title: "Suivi de commande — Snacki", robots: { index: false } };

export default function TrackPage() {
  return <TrackView />;
}
