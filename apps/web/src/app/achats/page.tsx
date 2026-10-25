import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { CancelPurchase, PurchaseForm, StockAdmin, SupplierAdmin } from "@/components/Achats";
import { CATEGORY_LABEL, qty, viewFrom, VIEWS, type View } from "@/lib/achats";
import { PAY_LABEL } from "@/lib/caisse";
import { mru, periodFrom, shortDay } from "@/lib/pilotage";
import { currentStaff, staffFetch } from "@/lib/server/staff";
import type { Ingredient, PurchaseList, Supplier } from "@/lib/types";

export const metadata: Metadata = { title: "Achats — Snacki", robots: { index: false, follow: false } };

const SUPPLIER = /^[1-9]\d{0,8}$/;

/**
 * Achats et stock (J16) : saisie des achats, stock des ingrédients, fournisseurs.
 * Gérante et admin, mêmes droits ; l'API vérifie le rôle à chaque appel et journalise tout.
 */
export default async function AchatsPage({
  searchParams,
}: {
  searchParams: Promise<{ vue?: string; start?: string; end?: string; supplier?: string }>;
}) {
  const me = await currentStaff();
  if (!me) redirect("/connexion");
  const today = new Date().toISOString().slice(0, 10); // Nouadhibou : UTC+0
  const params = await searchParams;
  const view: View = viewFrom(params.vue);
  const period = periodFrom(params, today);
  const supplier = SUPPLIER.test(params.supplier ?? "") ? params.supplier : "";

  let status = 0;
  const load = async <T,>(path: string): Promise<T | null> => {
    try {
      const r = await staffFetch(path);
      if (!r.ok) status = status || r.status;
      return r.ok ? ((await r.json()) as T) : null;
    } catch {
      status = status || 503;
      return null;
    }
  };
  const q = new URLSearchParams({ start: period.start, end: period.end, ...(supplier ? { supplier } : {}) });
  const [suppliers, ingredients, list] = await Promise.all([
    load<Supplier[]>("/v1/achats/fournisseurs"),
    load<Ingredient[]>("/v1/achats/ingredients"),
    view === "achats" ? load<PurchaseList>(`/v1/achats?${q.toString()}`) : Promise.resolve(null),
  ]);
  if (status === 401) redirect("/connexion");
  const low = (ingredients ?? []).filter((i) => i.low && i.active);

  return (
    <main className="app staff wide">
      <header className="staff-head">
        <div>
          <h1>Achats et stock</h1>
          <p className="muted">{me.display_name ?? me.email}</p>
        </div>
        <nav className="head-actions" aria-label="Navigation">
          <a className="ghost" href={`/pilotage?start=${period.start}&end=${period.end}`}>Pilotage</a>
          <a className="ghost" href="/historique?group=achats">Historique</a>
          <a className="ghost" href="/staff">Espace staff</a>
        </nav>
      </header>

      <nav className="period" aria-label="Rubriques">
        <div className="chips">
          {(Object.keys(VIEWS) as View[]).map((v) => (
            <a key={v} className="opt" aria-current={v === view ? "page" : undefined} href={`/achats?vue=${v}`}>{VIEWS[v]}</a>
          ))}
        </div>
      </nav>

      {status === 403 && <p className="alert bad">Les achats sont réservés à la gérante et à l&apos;admin.</p>}
      {status !== 0 && status !== 403 && <p className="alert bad">Achats momentanément indisponibles.</p>}
      {low.length > 0 && (
        <p className="alert" role="status">Stock bas : {low.map((i) => `${i.name} (${qty(i.stock_qty, i.unit)})`).join(" · ")}</p>
      )}

      {view === "achats" && suppliers && ingredients && (
        <>
          <PurchaseForm suppliers={suppliers} ingredients={ingredients} today={today} />

          <form className="filters" method="get" action="/achats">
            <input type="hidden" name="vue" value="achats" />
            <label>Du <input type="date" name="start" defaultValue={period.start} max={today} /></label>
            <label>Au <input type="date" name="end" defaultValue={period.end} max={today} /></label>
            <label>Fournisseur
              <select name="supplier" defaultValue={supplier}>
                <option value="">Tous</option>
                {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <button className="ghost" type="submit">Filtrer</button>
          </form>

          {list && (
            <section className="track scroll-x">
              <h2>Achats du {shortDay(list.start)} au {shortDay(list.end)} · {mru(list.total_mru)}</h2>
              {list.purchases.length === 0 && <p className="muted">Aucun achat sur cette période.</p>}
              {list.purchases.length > 0 && (
                <table className="table">
                  <thead><tr><th>Date</th><th>Fournisseur</th><th>Articles</th><th>Paiement</th><th>Total</th><th>Saisi par</th><th></th></tr></thead>
                  <tbody>
                    {list.purchases.map((p) => (
                      <tr key={p.id} className={p.cancelled_at ? "off" : ""}>
                        <td>{shortDay(p.purchase_day)}</td>
                        <td>{p.supplier ?? "—"}</td>
                        <td>
                          {p.lines.map((l) => `${l.label} ${qty(l.quantity)}${l.ingredient_id ? "" : ` (${CATEGORY_LABEL[l.category]})`}`).join(" · ")}
                          {p.note && <span className="muted"> · {p.note}</span>}
                          {p.cancel_reason && <span className="muted"> · annulé : {p.cancel_reason}</span>}
                        </td>
                        <td>{PAY_LABEL[p.payment_method]}</td>
                        <td className="num">{p.cancelled_at ? <s>{mru(p.total_mru)}</s> : mru(p.total_mru)}</td>
                        <td>{p.created_by}</td>
                        <td>{!p.cancelled_at && <CancelPurchase id={p.id} />}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {list.truncated && <p className="muted">Seuls les 300 achats les plus récents sont affichés : réduisez la période.</p>}
            </section>
          )}
        </>
      )}

      {view === "stock" && ingredients && <StockAdmin initial={ingredients} />}
      {view === "fournisseurs" && suppliers && <SupplierAdmin initial={suppliers} />}
    </main>
  );
}
