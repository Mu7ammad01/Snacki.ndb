import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AreaChart, ColumnChart } from "@/components/Charts";
import { PAY_LABEL } from "@/lib/caisse";
import { mru, periodFrom, presets, share, shortDay } from "@/lib/pilotage";
import { currentStaff, staffFetch } from "@/lib/server/staff";
import type { Forecast, Pilotage, Resume } from "@/lib/types";

/**
 * Barre horizontale en SVG : la CSP interdit les attributs style en ligne ; les largeurs passent
 * donc par des attributs SVG (x, width), les couleurs par des classes.
 */
function Bar({ parts, max }: { parts: { value: number; cls: string }[]; max: number }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  const width = share(total, max);
  let x = 0;
  return (
    <svg className="bt" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
      {parts.filter((p) => p.value > 0).map((p) => {
        const w = (p.value / total) * width;
        const rect = <rect key={p.cls} className={p.cls} x={x} y={0} width={w} height={10} />;
        x += w;
        return rect;
      })}
    </svg>
  );
}

export const metadata: Metadata = { title: "Pilotage — Snacki", robots: { index: false, follow: false } };

/**
 * Pilotage : page rendue par le serveur, sans JavaScript côté navigateur. La période passe dans
 * l'URL (dates validées) ; l'API vérifie le rôle (gérante ou admin) à chaque appel.
 */
export default async function PilotagePage({
  searchParams,
}: {
  searchParams: Promise<{ start?: string; end?: string; ia?: string }>;
}) {
  const me = await currentStaff();
  if (!me) redirect("/connexion");
  const today = new Date().toISOString().slice(0, 10); // Nouadhibou : UTC+0
  const params = await searchParams;
  const period = periodFrom(params, today);
  const wantAi = params.ia === "1";

  let data: Pilotage | null = null;
  let error: string | null = null;
  let status = 0;
  try {
    const r = await staffFetch(`/v1/pilotage?start=${period.start}&end=${period.end}`);
    status = r.status;
    if (r.ok) data = (await r.json()) as Pilotage;
  } catch {
    status = 503;
  }
  if (status === 401) redirect("/connexion");

  // J10 : prévisions et résumé ; s'ils manquent, le reste de la page s'affiche quand même.
  const optional = async <T,>(path: string): Promise<T | null> => {
    try {
      const r = await staffFetch(path);
      return r.ok ? ((await r.json()) as T) : null;
    } catch {
      return null;
    }
  };
  const [forecast, resume] = data
    ? await Promise.all([
        optional<Forecast>("/v1/pilotage/previsions"),
        optional<Resume>(`/v1/pilotage/resume?day=${period.end}${wantAi ? "&ia=true" : ""}`),
      ])
    : [null, null];
  const fcMax = Math.max(0, ...(forecast?.days ?? []).map((d) => d.units));
  if (status === 403) error = "Le pilotage est réservé à la gérante et à l'admin.";
  else if (!data) error = "Chiffres momentanément indisponibles.";

  const dayMax = Math.max(0, ...(data?.by_day ?? []).map((d) => d.app_mru + d.comptoir_mru + d.historique_mru));
  const topMax = Math.max(0, ...(data?.top ?? []).map((t) => t.quantity));
  const payMax = Math.max(0, ...(data?.payments ?? []).map((p) => p.amount_mru));

  return (
    <main className="app staff wide">
      <header className="staff-head">
        <div>
          <h1>Pilotage</h1>
          <p className="muted">{me.display_name ?? me.email}</p>
        </div>
        <nav className="head-actions" aria-label="Actions">
          <a className="primary" href={`/pilotage/rapport?start=${period.start}&end=${period.end}`}>Générer un rapport</a>
          <a className="ghost" href={`/historique?start=${period.start}&end=${period.end}`}>Historique</a>
          <a className="ghost" href="/staff">Espace staff</a>
        </nav>
      </header>

      <form className="period" method="get" action="/pilotage">
        <div className="chips">
          {presets(today).map((p) => (
            <a key={p.label} className="opt" aria-current={p.period.start === period.start && p.period.end === period.end ? "page" : undefined}
              href={`/pilotage?start=${p.period.start}&end=${p.period.end}`}>{p.label}</a>
          ))}
        </div>
        <label>Du <input type="date" name="start" defaultValue={period.start} /></label>
        <label>au <input type="date" name="end" defaultValue={period.end} max={today} /></label>
        <button className="ghost" type="submit">Afficher</button>
      </form>

      {error && <p className="alert bad" role="status">{error}</p>}

      {data && (
        <>
          <section className="kpis">
            <div><span>Chiffre d&apos;affaires</span><b>{mru(data.revenue_mru)}</b></div>
            <div><span>Commandes</span><b>{data.orders}</b></div>
            <div><span>Panier moyen</span><b>{mru(data.average_basket_mru)}</b></div>
            <div><span>Aujourd&apos;hui</span><b>{mru(data.today_mru)}</b></div>
            <div><span>Cumul depuis l&apos;ouverture</span><b>{mru(data.all_time_mru)}</b></div>
          </section>

          <section className="charts">
            <div className="track">
              <h2>Chiffre d&apos;affaires par jour</h2>
              {data.by_day.length === 0 ? <p className="muted">Aucune vente sur cette période.</p> : (
                <AreaChart title="Chiffre d'affaires par jour, en MRU"
                  points={data.by_day.map((d) => ({ label: shortDay(d.day), value: d.app_mru + d.comptoir_mru + d.historique_mru }))} />
              )}
            </div>
            <div className="track">
              <h2>Commandes par jour</h2>
              {data.by_day.length === 0 ? <p className="muted">Aucune commande sur cette période.</p> : (
                <ColumnChart title="Nombre de commandes par jour" points={data.by_day.map((d) => ({ label: shortDay(d.day), value: d.orders }))} />
              )}
            </div>
          </section>

          {resume && (
            <section className="track">
              <h2>Résumé du {shortDay(resume.day)}</h2>
              <p>{resume.text}</p>
              {resume.warnings.map((w) => <p key={w} className="muted">{w}</p>)}
              <p className="muted">
                {resume.engine === "gemini"
                  ? "Reformulé par l'IA ; chaque chiffre a été vérifié dans les ventes."
                  : "Résumé calculé directement à partir des ventes."}
                {resume.ai_available && resume.engine !== "gemini" && (
                  <> <a href={`/pilotage?start=${period.start}&end=${period.end}&ia=1`}>Reformuler avec l&apos;IA</a></>
                )}
              </p>
            </section>
          )}

          {forecast && (
            <section className="track">
              <h2>Prévisions (7 jours)</h2>
              <ul className="bars">
                {forecast.days.map((d) => (
                  <li key={d.day}>
                    <span className="bl">{d.weekday.slice(0, 3)} {shortDay(d.day)}</span>
                    <Bar max={fcMax} parts={[{ value: d.units, cls: "b-hist" }]} />
                    <span className="bv">≈ {d.units} art.</span>
                  </li>
                ))}
              </ul>
              {forecast.days[0]?.items.length > 0 && (
                <p>À préparer aujourd&apos;hui : {forecast.days[0].items.map((i) => `${i.label} ${i.quantity}`).join(" · ")}</p>
              )}
              <p className="muted">
                {forecast.reliability === "bonne" && "Fiabilité : bonne (meilleure que « comme la semaine dernière » sur 4 semaines)."}
                {forecast.reliability === "indicative" && "Fiabilité : indicative ; à corriger avec votre expérience."}
                {forecast.reliability === "insuffisante" && "Pas encore assez de jours de ventes pour une prévision fiable (14 au moins)."}
                {forecast.backtest.model_error !== null && ` Écart moyen : ${forecast.backtest.model_error} articles par jour (méthode simple : ${forecast.backtest.naive_error}).`}
              </p>
            </section>
          )}

          <section className="track">
            <h2>Détail par jour et par source</h2>
            {data.by_day.length === 0 && <p className="muted">Aucune vente sur cette période.</p>}
            <ul className="bars">
              {data.by_day.map((d) => {
                const total = d.app_mru + d.comptoir_mru + d.historique_mru;
                return (
                  <li key={d.day}>
                    <span className="bl">{shortDay(d.day)}</span>
                    <Bar max={dayMax} parts={[
                      { value: d.app_mru, cls: "b-app" },
                      { value: d.comptoir_mru, cls: "b-comptoir" },
                      { value: d.historique_mru, cls: "b-hist" },
                    ]} />
                    <span className="bv">{mru(total)}</span>
                  </li>
                );
              })}
            </ul>
            <p className="legend"><i className="b-app" /> app <i className="b-comptoir" /> comptoir <i className="b-hist" /> historique Excel</p>
          </section>

          <section className="track">
            <h2>Produits les plus vendus</h2>
            <ul className="bars">
              {data.top.map((t) => (
                <li key={t.product_id ?? "hors-menu"}>
                  <span className="bl">{t.label}</span>
                  <Bar max={topMax} parts={[{ value: t.quantity, cls: "b-app" }]} />
                  <span className="bv">{t.quantity}</span>
                </li>
              ))}
            </ul>
            <p className="muted">Quantités vendues (app, comptoir et historique). « Hors menu » : desserts et articles non reconnus dans l&apos;Excel.</p>
          </section>

          <section className="track">
            <h2>Moyens de paiement</h2>
            {data.payments.length === 0 && <p className="muted">Aucun encaissement dans l&apos;app sur cette période.</p>}
            <ul className="bars">
              {data.payments.map((p) => (
                <li key={p.method}>
                  <span className="bl">{PAY_LABEL[p.method] ?? p.method}</span>
                  <Bar max={payMax} parts={[{ value: p.amount_mru, cls: "b-comptoir" }]} />
                  <span className="bv">{mru(p.amount_mru)} · {p.count}</span>
                </li>
              ))}
            </ul>
            <p className="muted">L&apos;historique Excel ne précise pas le moyen de paiement.</p>
          </section>

          <section className="track">
            <h2>Fidélité</h2>
            <div className="kpis">
              <div><span>Tampons donnés</span><b>{data.loyalty.stamps}</b></div>
              <div><span>Commandes offertes</span><b>{data.loyalty.rewards}</b></div>
              <div><span>Montant offert</span><b>{mru(data.loyalty.discount_mru)}</b></div>
              <div><span>Cartes actives (total)</span><b>{data.loyalty.active_cards}</b></div>
            </div>
          </section>

          {data.history_first && (
            <p className="muted small-note">Historique importé : du {shortDay(data.history_first)} au {data.history_last && shortDay(data.history_last)}.</p>
          )}
        </>
      )}
    </main>
  );
}
