import type { Metadata } from "next";
import { redirect } from "next/navigation";

import CaisseBoard from "@/components/CaisseBoard";
import { apiFetch } from "@/lib/server/api";
import { currentStaff } from "@/lib/server/staff";
import type { Product } from "@/lib/types";

export const metadata: Metadata = { title: "Caisse — Snacki", robots: { index: false, follow: false } };

async function loadMenu(): Promise<Product[]> {
  try {
    const r = await apiFetch("/v1/menu");
    return r.ok ? ((await r.json()) as { products: Product[] }).products : [];
  } catch {
    return [];
  }
}

/** Caisse : réservée au staff connecté. Chaque action est revérifiée par l'API (rôle et état). */
export default async function CaissePage() {
  const me = await currentStaff();
  if (!me) redirect("/connexion");
  return (
    <main className="app staff wide">
      <header className="staff-head">
        <div>
          <h1>Caisse</h1>
          <p className="muted">{me.display_name ?? me.email}</p>
        </div>
        <a className="ghost" href="/staff">Espace staff</a>
      </header>
      <CaisseBoard me={me} products={await loadMenu()} />
    </main>
  );
}
