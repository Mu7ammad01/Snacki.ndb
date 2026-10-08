import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { periodFrom } from "@/lib/pilotage";
import { currentStaff, staffFetch } from "@/lib/server/staff";
import type { History } from "@/lib/types";

export const metadata: Metadata = { title: "Historique — Snacki", robots: { index: false, follow: false } };

const GROUP = /^[a-z]{2,20}$/;
const PERSON = /^[1-9]\d{0,8}$/;
const when = (at: string) => `${at.slice(8, 10)}/${at.slice(5, 7)} ${at.slice(11, 16)}`;

/** Historique (v1.1, réunion 5, demande 4) : qui a fait quoi et quand, filtrable. */
export default async function HistoriquePage({
  searchParams,
}: {
  searchParams: Promise<{ start?: string; end?: string; person?: string; group?: string }>;
}) {
  const me = await currentStaff();
  if (!me) redirect("/connexion");
  const today = new Date().toISOString().slice(0, 10);
  const params = await searchParams;
  const period = periodFrom(params, today);
  const person = PERSON.test(params.person ?? "") ? params.person : "";
  const group = GROUP.test(params.group ?? "") ? params.group : "";
  const q = new URLSearchParams({ start: period.start, end: period.end, ...(person ? { person } : {}), ...(group ? { group } : {}) });

  let data: History | null = null;
  let status = 0;
  try {
    const r = await staffFetch(`/v1/historique?${q.toString()}`);
    status = r.status;
    if (r.ok) data = (await r.json()) as History;
  } catch {
    status = 503;
  }
  if (status === 401) redirect("/connexion");

  return (
    <main className="app staff wide">
      <header className="staff-head">
        <div>
          <h1>Historique</h1>
          <p className="muted">Toutes les actions de l&apos;équipe, avec la date, l&apos;heure et la personne.</p>
        </div>
        <nav className="head-actions" aria-label="Navigation">
          <a className="ghost" href={`/pilotage?start=${period.start}&end=${period.end}`}>Pilotage</a>
          <a className="ghost" href="/staff">Espace staff</a>
        </nav>
      </header>

      <form className="filters" method="get" action="/historique">
        <label>Du <input type="date" name="start" defaultValue={period.start} max={today} /></label>
        <label>Au <input type="date" name="end" defaultValue={period.end} max={today} /></label>
        <label>Personne
          <select name="person" defaultValue={person}>
            <option value="">Tout le monde</option>
            {data?.people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label>Type d&apos;action
          <select name="group" defaultValue={group}>
            <option value="">Toutes</option>
            {Object.entries(data?.groups ?? {}).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </select>
        </label>
        <button className="ghost" type="submit">Filtrer</button>
      </form>

      {status === 403 && <p className="alert bad">L&apos;historique est réservé à la gérante et à l&apos;admin.</p>}
      {!data && status !== 403 && <p className="alert bad">Historique momentanément indisponible.</p>}
      {data && (
        <section className="track scroll-x">
          {data.entries.length === 0 && <p className="muted">Aucune action pour ces filtres.</p>}
          {data.entries.length > 0 && (
            <table className="table">
              <thead><tr><th>Date et heure</th><th>Personne</th><th>Action</th><th>Sur</th><th>Détail</th></tr></thead>
              <tbody>
                {data.entries.map((e, i) => (
                  <tr key={e.at + i}>
                    <td>{when(e.at)}</td><td>{e.actor}</td><td>{e.label}</td><td>{e.target ?? ""}</td><td className="muted">{e.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {data.truncated && <p className="muted">Seules les 500 actions les plus récentes sont affichées : réduisez la période ou filtrez.</p>}
        </section>
      )}
    </main>
  );
}
