import type { Metadata } from "next";
import { redirect } from "next/navigation";

import TeamAdmin from "@/components/TeamAdmin";
import { currentStaff, staffFetch } from "@/lib/server/staff";
import { ROLE_LABEL, sectionsFor, type StaffMember } from "@/lib/staff";

export const metadata: Metadata = { title: "Espace staff — Snacki", robots: { index: false, follow: false } };

/** Accueil du staff. Ce qui est affiché dépend du rôle, mais c'est l'API qui contrôle chaque action. */
export default async function StaffHome() {
  const me = await currentStaff();
  if (!me) redirect("/connexion");
  const show = sectionsFor(me.role);

  let team: StaffMember[] = [];
  if (show.equipe) {
    const r = await staffFetch("/v1/staff");
    if (r.ok) team = (await r.json()) as StaffMember[];
  }

  return (
    <main className="app staff">
      <header className="staff-head">
        <div>
          <h1>Bonjour {me.display_name ?? me.email}</h1>
          <p className="muted">
            {ROLE_LABEL[me.role]} · {me.email}
          </p>
        </div>
        <form method="post" action="/auth/logout">
          <button className="ghost" type="submit">Se déconnecter</button>
        </form>
      </header>

      <section className="staff-grid">
        {show.caisse && (
          <a className="track staff-link" href="/caisse">
            <h2>Caisse →</h2>
            <p className="muted">Commandes du jour en direct, saisie au comptoir, encaissement.</p>
          </a>
        )}
        {show.pilotage && (
          <div className="track">
            <h2>Pilotage</h2>
            <p className="muted">Chiffre d&apos;affaires, produits les plus vendus, historique. Arrive à J8.</p>
          </div>
        )}
      </section>

      {show.equipe && <TeamAdmin me={me} initial={team} />}
    </main>
  );
}
