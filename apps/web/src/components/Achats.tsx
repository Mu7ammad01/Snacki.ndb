"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import {
  buildPurchase,
  CATEGORY_LABEL,
  draftTotal,
  emptyLine,
  FREE_CATEGORIES,
  parseQty,
  qty,
  UNIT_LABEL,
  type LineDraft,
  type PurchaseDraft,
} from "@/lib/achats";
import { PAY_LABEL } from "@/lib/caisse";
import { mru } from "@/lib/pilotage";
import type { Ingredient, PaymentMethod, PurchaseCategory, StockUnit, Supplier } from "@/lib/types";
import { oneLine } from "@/lib/validate";

type Msg = { text: string; bad: boolean } | null;

/** Appel d'une route du serveur web ; 401 renvoie vers la connexion, l'erreur de l'API est montrée. */
function useCall() {
  const [msg, setMsg] = useState<Msg>(null);
  const [busy, setBusy] = useState(false);
  async function call<T>(url: string, method: "POST" | "PATCH", body: object): Promise<T | null> {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = (await r.json().catch(() => ({}))) as T & { detail?: unknown };
      if (r.status === 401) { window.location.assign("/connexion"); return null; }
      if (!r.ok) {
        const detail = typeof data.detail === "string" ? data.detail : r.status === 422 ? "Saisie invalide : vérifiez les champs" : "Action refusée";
        setMsg({ text: detail, bad: true });
        return null;
      }
      return data;
    } catch {
      setMsg({ text: "Service momentanément indisponible", bad: true });
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { msg, setMsg, busy, call };
}

const Status = ({ msg }: { msg: Msg }) => (msg ? <p className={msg.bad ? "alert bad" : "alert"} role="status">{msg.text}</p> : null);

// --- Saisie d'un achat ------------------------------------------------------------------------

export function PurchaseForm({ suppliers, ingredients, today }: { suppliers: Supplier[]; ingredients: Ingredient[]; today: string }) {
  const router = useRouter();
  const { msg, setMsg, busy, call } = useCall();
  const fresh = (): PurchaseDraft => ({ day: today, supplierId: "", payment: "cash", note: "", lines: [emptyLine()] });
  const [d, setD] = useState<PurchaseDraft>(fresh);
  const active = ingredients.filter((i) => i.active);
  const unitOf = (id: string) => active.find((i) => String(i.id) === id)?.unit;

  const setLine = (n: number, change: Partial<LineDraft>) =>
    setD((x) => ({ ...x, lines: x.lines.map((l, i) => (i === n ? { ...l, ...change } : l)) }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const built = buildPurchase(d);
    if (!built.ok) { setMsg({ text: built.error, bad: true }); return; }
    const saved = await call<{ id: number; total_mru: number }>("/api/achats", "POST", built.body);
    if (saved) {
      setD(fresh());
      setMsg({ text: `Achat n° ${saved.id} enregistré : ${mru(saved.total_mru)}.`, bad: false });
      router.refresh();
    }
  }

  return (
    <form className="track purchase-form" onSubmit={submit}>
      <h2>Nouvel achat</h2>
      <div className="filters">
        <label>Date<input type="date" required value={d.day} max={today} onChange={(e) => setD({ ...d, day: e.target.value })} /></label>
        <label>Fournisseur
          <select value={d.supplierId} onChange={(e) => setD({ ...d, supplierId: e.target.value })}>
            <option value="">Sans fournisseur</option>
            {suppliers.filter((s) => s.active).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label>Paiement
          <select value={d.payment} onChange={(e) => setD({ ...d, payment: e.target.value as PaymentMethod })}>
            {(Object.keys(PAY_LABEL) as PaymentMethod[]).map((p) => <option key={p} value={p}>{PAY_LABEL[p]}</option>)}
          </select>
        </label>
      </div>

      <ol className="purchase-lines">
        {d.lines.map((l, n) => (
          <li key={n}>
            <label>Article
              <select aria-label={`Article de la ligne ${n + 1}`} value={l.ingredientId} onChange={(e) => setLine(n, { ingredientId: e.target.value })}>
                <option value="">Autre (libellé libre)</option>
                {active.map((i) => <option key={i.id} value={i.id}>{i.name} ({UNIT_LABEL[i.unit]})</option>)}
              </select>
            </label>
            {!l.ingredientId && (
              <>
                <label>Libellé<input maxLength={60} placeholder="Gaz, gobelets…" value={l.label} onChange={(e) => setLine(n, { label: e.target.value })} /></label>
                <label>Catégorie
                  <select value={l.category} onChange={(e) => setLine(n, { category: e.target.value as PurchaseCategory })}>
                    {FREE_CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
                  </select>
                </label>
              </>
            )}
            <label>Quantité{l.ingredientId ? ` (${UNIT_LABEL[unitOf(l.ingredientId) ?? "piece"]})` : ""}
              <input inputMode="decimal" required value={l.quantity} onChange={(e) => setLine(n, { quantity: e.target.value })}
                aria-invalid={l.quantity !== "" && parseQty(l.quantity) === null} />
            </label>
            <label>Montant (MRU)<input inputMode="numeric" required value={l.amount} onChange={(e) => setLine(n, { amount: e.target.value })} /></label>
            {d.lines.length > 1 && (
              <button type="button" className="ghost" onClick={() => setD({ ...d, lines: d.lines.filter((_, i) => i !== n) })}>Retirer</button>
            )}
          </li>
        ))}
      </ol>
      <button type="button" className="ghost add-line" disabled={d.lines.length >= 30}
        onClick={() => setD({ ...d, lines: [...d.lines, emptyLine()] })}>+ Ajouter une ligne</button>

      <div className="filters">
        <label className="grow">Note (facultatif)<input maxLength={160} value={d.note} onChange={(e) => setD({ ...d, note: e.target.value })} /></label>
      </div>
      <Status msg={msg} />
      <button className="primary" type="submit" disabled={busy}>Enregistrer l&apos;achat · {mru(draftTotal(d.lines))}</button>
      <p className="muted">Les quantités d&apos;ingrédients entrent en stock. Une erreur se corrige en annulant l&apos;achat puis en le saisissant à nouveau.</p>
    </form>
  );
}

export function CancelPurchase({ id }: { id: number }) {
  const router = useRouter();
  const { msg, busy, call } = useCall();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (await call(`/api/achats/${id}/annuler`, "POST", { reason: oneLine(reason) })) router.refresh();
  }

  if (!open) return <button type="button" className="ghost small" onClick={() => setOpen(true)}>Annuler…</button>;
  return (
    <form className="inline-form" onSubmit={submit}>
      <input aria-label={`Motif d'annulation de l'achat ${id}`} placeholder="Motif (3 caractères au moins)" minLength={3} maxLength={160}
        required value={reason} onChange={(e) => setReason(e.target.value)} />
      <button className="ghost small" type="submit" disabled={busy}>Confirmer</button>
      <button className="ghost small" type="button" onClick={() => setOpen(false)}>Garder</button>
      <Status msg={msg} />
    </form>
  );
}

// --- Stock ---------------------------------------------------------------------------------

export function StockAdmin({ initial }: { initial: Ingredient[] }) {
  const { msg, setMsg, busy, call } = useCall();
  const [items, setItems] = useState(initial);
  const [name, setName] = useState("");
  const [unit, setUnit] = useState<StockUnit>("kg");
  const [alert, setAlert] = useState("");
  const [counting, setCounting] = useState<{ id: number; quantity: string; reason: string } | null>(null);
  const replace = (i: Ingredient) => setItems((xs) => xs.map((x) => (x.id === i.id ? i : x)));

  async function add(e: FormEvent) {
    e.preventDefault();
    const threshold = alert.trim() ? parseQty(alert) : null;
    if (alert.trim() && threshold === null) { setMsg({ text: "Seuil d'alerte invalide", bad: true }); return; }
    const added = await call<Ingredient>("/api/achats/ingredients", "POST", { name: oneLine(name), unit, alert_qty: threshold });
    if (added) {
      setItems((xs) => [...xs, added].sort((a, b) => a.name.localeCompare(b.name, "fr")));
      setName("");
      setAlert("");
      setMsg({ text: `${added.name} ajouté au stock.`, bad: false });
    }
  }

  async function inventory(e: FormEvent) {
    e.preventDefault();
    if (!counting) return;
    const text = counting.quantity.trim().replace(",", ".");
    const quantity = /^0+(\.0+)?$/.test(text) ? 0 : parseQty(text);
    if (quantity === null) { setMsg({ text: "Quantité comptée invalide", bad: true }); return; }
    const updated = await call<Ingredient>(`/api/achats/ingredients/${counting.id}/inventaire`, "POST",
      { quantity, reason: oneLine(counting.reason) });
    if (updated) { replace(updated); setCounting(null); setMsg({ text: `Stock de ${updated.name} corrigé.`, bad: false }); }
  }

  async function toggle(i: Ingredient) {
    const updated = await call<Ingredient>(`/api/achats/ingredients/${i.id}`, "PATCH", { active: !i.active });
    if (updated) replace(updated);
  }

  return (
    <section className="track">
      <h2>Stock des ingrédients</h2>
      <p className="muted">Le stock augmente à chaque achat. Faites un inventaire pour le caler sur le comptage réel ; l&apos;écart est tracé.</p>
      <Status msg={msg} />
      <div className="scroll-x">
        <table className="table">
          <thead><tr><th>Ingrédient</th><th>Stock</th><th>Alerte sous</th><th></th></tr></thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.id} className={i.active ? "" : "off"}>
                <td>{i.name}{i.low && <span className="tag bad"> stock bas</span>}{!i.active && <span className="muted"> · désactivé</span>}</td>
                <td className="num">{qty(i.stock_qty, i.unit)}</td>
                <td className="num">{i.alert_qty === null ? "—" : qty(i.alert_qty, i.unit)}</td>
                <td>
                  {counting?.id === i.id ? (
                    <form className="inline-form" onSubmit={inventory}>
                      <input aria-label={`Quantité comptée de ${i.name}`} inputMode="decimal" required placeholder={`Compté (${UNIT_LABEL[i.unit]})`}
                        value={counting.quantity} onChange={(e) => setCounting({ ...counting, quantity: e.target.value })} />
                      <input aria-label="Motif de l'inventaire" required minLength={3} maxLength={160} placeholder="Motif"
                        value={counting.reason} onChange={(e) => setCounting({ ...counting, reason: e.target.value })} />
                      <button className="ghost small" type="submit" disabled={busy}>Valider</button>
                      <button className="ghost small" type="button" onClick={() => setCounting(null)}>Fermer</button>
                    </form>
                  ) : (
                    <span className="row-actions">
                      {i.active && <button type="button" className="ghost small" onClick={() => setCounting({ id: i.id, quantity: "", reason: "Inventaire" })}>Inventaire</button>}
                      <button type="button" className="ghost small" disabled={busy} onClick={() => toggle(i)}>{i.active ? "Désactiver" : "Réactiver"}</button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length === 0 && <p className="muted">Aucun ingrédient suivi pour l&apos;instant.</p>}

      <form className="filters" onSubmit={add}>
        <label>Nouvel ingrédient<input required minLength={2} maxLength={60} value={name} onChange={(e) => setName(e.target.value)} placeholder="Avocat" /></label>
        <label>Unité
          <select value={unit} onChange={(e) => setUnit(e.target.value as StockUnit)}>
            {(Object.keys(UNIT_LABEL) as StockUnit[]).map((u) => <option key={u} value={u}>{UNIT_LABEL[u]}</option>)}
          </select>
        </label>
        <label>Alerte sous (facultatif)<input inputMode="decimal" value={alert} onChange={(e) => setAlert(e.target.value)} placeholder="2" /></label>
        <button className="ghost" type="submit" disabled={busy}>Ajouter</button>
      </form>
    </section>
  );
}

// --- Fournisseurs ----------------------------------------------------------------------------

export function SupplierAdmin({ initial }: { initial: Supplier[] }) {
  const { msg, setMsg, busy, call } = useCall();
  const [items, setItems] = useState(initial);
  const [form, setForm] = useState({ name: "", phone: "", note: "" });

  async function add(e: FormEvent) {
    e.preventDefault();
    const note = oneLine(form.note);
    const added = await call<Supplier>("/api/achats/fournisseurs", "POST",
      { name: oneLine(form.name), phone: form.phone.trim() || null, ...(note ? { note } : {}) });
    if (added) {
      setItems((xs) => [...xs, added].sort((a, b) => a.name.localeCompare(b.name, "fr")));
      setForm({ name: "", phone: "", note: "" });
      setMsg({ text: `${added.name} ajouté.`, bad: false });
    }
  }

  async function toggle(s: Supplier) {
    const updated = await call<Supplier>(`/api/achats/fournisseurs/${s.id}`, "PATCH", { active: !s.active });
    if (updated) setItems((xs) => xs.map((x) => (x.id === updated.id ? updated : x)));
  }

  return (
    <section className="track">
      <h2>Fournisseurs</h2>
      <Status msg={msg} />
      <ul className="team">
        {items.map((s) => (
          <li key={s.id} className={s.active ? "" : "off"}>
            <div>
              <b>{s.name}</b>
              <span className="muted">{[s.phone, s.note].filter(Boolean).join(" · ") || "—"}{s.active ? "" : " · désactivé"}</span>
            </div>
            <div className="team-actions">
              <button type="button" className="ghost" disabled={busy} onClick={() => toggle(s)}>{s.active ? "Désactiver" : "Réactiver"}</button>
            </div>
          </li>
        ))}
      </ul>
      {items.length === 0 && <p className="muted">Aucun fournisseur pour l&apos;instant.</p>}
      <form className="filters" onSubmit={add}>
        <label>Nom<input required minLength={2} maxLength={80} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>Téléphone (facultatif)<input inputMode="tel" maxLength={14} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="36 12 34 56" /></label>
        <label className="grow">Produits, remarques<input maxLength={160} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="Fruits, livraison le matin" /></label>
        <button className="ghost" type="submit" disabled={busy}>Ajouter</button>
      </form>
    </section>
  );
}
