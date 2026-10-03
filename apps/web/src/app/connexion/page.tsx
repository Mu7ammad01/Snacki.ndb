import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentStaff } from "@/lib/server/staff";

export const metadata: Metadata = { title: "Espace staff — Snacki", robots: { index: false, follow: false } };

const MESSAGES: Record<string, { text: string; bad: boolean }> = {
  refusee: { text: "Connexion refusée. Utilisez l'adresse Google enregistrée par l'administrateur.", bad: true },
  indisponible: { text: "Connexion momentanément indisponible. Réessayez dans un instant.", bad: true },
  deconnecte: { text: "Vous êtes déconnecté.", bad: false },
};

export default async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  if (await currentStaff()) redirect("/staff");
  const q = await searchParams;
  const msg = q.deconnecte ? MESSAGES.deconnecte : MESSAGES[q.erreur ?? ""];
  return (
    <main className="app staff">
      <div className="track">
        <h1>Espace staff</h1>
        <p className="muted">Caisse, commandes et pilotage de Snacki. Réservé à l&apos;équipe.</p>
        {msg && <p className={msg.bad ? "alert bad" : "alert"} role="status">{msg.text}</p>}
        {/* Un lien et non un formulaire : la CSP n'autorise les formulaires que vers ce site. */}
        <a className="primary" href="/auth/login">Se connecter avec Google</a>
        <p className="muted small-note">Aucun mot de passe Snacki : votre compte Google suffit.</p>
      </div>
    </main>
  );
}
