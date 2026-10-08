import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AreaChart, ColumnChart } from "@/components/Charts";
import PrintButton from "@/components/PrintButton";
import { PAY_LABEL } from "@/lib/caisse";
import { mru, periodFrom, presets, shortDay } from "@/lib/pilotage";
import { currentStaff, staffFetch } from "@/lib/server/staff";
import type { Pilotage } from "@/lib/types";

export const metadata: Metadata = { title: "Rapport — Snacki", robots: { index: false, follow: false } };

const longDay = (day: string) => `${day.slice(8, 10)}/${day.slice(5, 7)}/${day.slice(0, 4)}`;

/** Rapport du pilotage (v1.1, réunion 5) : période au choix, Excel ou PDF, date de génération. */
export default async function RapportPage({ searchParams }: { searchParams: Promise<{ start?: string; end?: string }> }) {
  const me = await currentStaff();
  if (!me) redirect("/connexion");
  const today = new Date().toISOString().slice(0, 10); // Nouadhibou : UTC+0
  const period = periodFrom(await searchParams, today);
  let data: Pilotage | null = null;
  let status = 0;
  try {
    const r = await staffFetch(`/v1/pilotage?start=${period.start}&end=${period.end}`);
    status = r.status;
    if (r.ok) data = (await r.json()) as Pilotage;
  } catch {
    status = 503;
  }
  if (status === 401) redirect("/connexion");
  const generated = new Date().toISOString().replace("T", " à ").slice(0, 18);
  const q = `start=${period.start}&end=${period.end}`;

  return (
    <main className="app staff wide">
      <header className="report-head">
        <div>
          <h1>Rapport Snacki</h1>
          <p>Du {longDay(period.start)} au {longDay(period.end)}</p>
          <p className="report-meta">Généré le {longDay(generated.slice(0, 10))} {generated.slice(10)} (heure de Nouadhibou) par {me.display_name ?? me.email}</p>
        </div>
        <nav className="head-actions no-print" aria-label="Rapport">
          <a className="primary" href={`/api/pilotage/rapport?${q}`}>Télécharger Excel</a>
          <PrintButton label="Enregistrer en PDF" />
          <a className="ghost" href={`/pilotage?${q}`}>Retour au pilotage</a>
        </nav>
      </header>

      <form className="period no-print" method="get" action="/pilotage/rapport">
        <div className="chips">
          {presets(today).map((p) => (
            <a key={p.label} className="opt" aria-current={p.period.start === period.start && p.period.end === period.end ? "page" : undefined}
              href={`/pilotage/rapport?start=${p.period.start}&end=${p.period.end}`}>{p.label}</a>
          ))}
        </div>
        <label>Du <input type="date" name="start" defaultValue={period.start} /></label>
        <label>au <input type="date" name="end" defaultValue={period.end} max={today} /></label>
        <button className="ghost" type="submit">Afficher</button>
      </form>

      {status === 403 && <p className="alert bad">Le rapport est réservé à la gérante et à l&apos;admin.</p>}
      {!data && status !== 403 && <p className="alert bad">Chiffres momentanément indisponibles.</p>}
      {data && (
        <>
          <section className="kpis">
            <div><span>Chiffre d&apos;affaires</span><b>{mru(data.revenue_mru)}</b></div>
            <div><span>Commandes</span><b>{data.orders}</b></div>
            <div><span>Panier moyen</span><b>{mru(data.average_basket_mru)}</b></div>
            <div><span>Cumul depuis l&apos;ouverture</span><b>{mru(data.all_time_mru)}</b></div>
          </section>
          <section className="charts">
            <div className="track">
              <h2>Chiffre d&apos;affaires par jour</h2>
              <AreaChart title="Chiffre d'affaires par jour, en MRU"
                points={data.by_day.map((d) => ({ label: shortDay(d.day), value: d.app_mru + d.comptoir_mru + d.historique_mru }))} />
            </div>
            <div className="track">
              <h2>Commandes par jour</h2>
              <ColumnChart title="Nombre de commandes par jour" points={data.by_day.map((d) => ({ label: shortDay(d.day), value: d.orders }))} />
            </div>
          </section>
          <section className="track scroll-x">
            <h2>Produits les plus vendus</h2>
            <table className="table">
              <thead><tr><th>Produit</th><th className="num">Quantité</th><th className="num">Montant app et comptoir</th></tr></thead>
              <tbody>{data.top.map((t) => <tr key={t.product_id ?? "hors-menu"}><td>{t.label}</td><td className="num">{t.quantity}</td><td className="num">{mru(t.revenue_mru)}</td></tr>)}</tbody>
            </table>
          </section>
          <section className="track scroll-x">
            <h2>Moyens de paiement</h2>
            <table className="table">
              <thead><tr><th>Moyen</th><th className="num">Encaissements</th><th className="num">Montant</th></tr></thead>
              <tbody>{data.payments.map((p) => <tr key={p.method}><td>{PAY_LABEL[p.method] ?? p.method}</td><td className="num">{p.count}</td><td className="num">{mru(p.amount_mru)}</td></tr>)}</tbody>
            </table>
          </section>
          <section className="track">
            <h2>Fidélité</h2>
            <p>{data.loyalty.stamps} tampon(s) donné(s), {data.loyalty.rewards} commande(s) offerte(s) pour {mru(data.loyalty.discount_mru)}.</p>
          </section>
        </>
      )}
    </main>
  );
}
