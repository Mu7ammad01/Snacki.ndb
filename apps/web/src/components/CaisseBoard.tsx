"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import {
  DELAYS,
  PAY_LABEL,
  STATUS_LABEL,
  actionsFor,
  columnOf,
  hhmm,
  newArrivals,
  parseFee,
  telLink,
  type Column,
} from "@/lib/caisse";
import type { StaffMe } from "@/lib/staff";
import type { CaisseOrder, PaymentMethod, Product } from "@/lib/types";

const REFRESH_MS = 5_000;
const PAYS = Object.keys(PAY_LABEL) as PaymentMethod[];
type Panel = null | { id: number; mode: "accept" | "refuse" | "cancel" | "pay" };

/** Bip court généré par le navigateur (aucun fichier son à charger). */
function beep(ctx: AudioContext | null) {
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.frequency.value = 880;
  gain.gain.setValueAtTime(0.25, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.6);
}

export default function CaisseBoard({ me, products }: { me: StaffMe; products: Product[] }) {
  const [orders, setOrders] = useState<CaisseOrder[]>([]);
  const [column, setColumn] = useState<Column>("todo");
  const [panel, setPanel] = useState<Panel>(null);
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [alerts, setAlerts] = useState(false);
  const [counter, setCounter] = useState(false);
  const known = useRef<Set<number> | null>(null);
  const audio = useRef<AudioContext | null>(null);
  const names = new Map(products.map((p) => [p.id, p.name_fr]));

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/caisse/orders", { cache: "no-store" });
      if (r.status === 401) { window.location.assign("/connexion"); return; }
      if (!r.ok) return;
      const data = (await r.json()) as { orders: CaisseOrder[] };
      const fresh = known.current ? newArrivals(known.current, data.orders) : [];
      known.current = new Set(data.orders.map((o) => o.id));
      if (fresh.length) {
        beep(audio.current);
        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          new Notification("Snacki · nouvelle commande", { body: `${fresh.length} commande(s) à accepter` });
        }
      }
      setOrders(data.orders);
    } catch {
      setMsg({ text: "Connexion perdue, nouvel essai dans 5 s", bad: true });
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  async function enableAlerts() {
    // Le navigateur n'autorise le son qu'après un geste de l'utilisateur.
    audio.current = new AudioContext();
    beep(audio.current);
    if (typeof Notification !== "undefined") await Notification.requestPermission();
    setAlerts(true);
  }

  async function post(url: string, body?: object) {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body ?? {}),
      });
      const data = (await r.json().catch(() => ({}))) as { detail?: unknown };
      if (r.status === 401) { window.location.assign("/connexion"); return false; }
      if (!r.ok) {
        setMsg({ text: typeof data.detail === "string" ? data.detail : "Action refusée", bad: true });
        return false;
      }
      setPanel(null);
      await load();
      return true;
    } catch {
      setMsg({ text: "Service momentanément indisponible", bad: true });
      return false;
    } finally {
      setBusy(false);
    }
  }

  const act = (o: CaisseOrder, name: string, body?: object) => post(`/api/caisse/orders/${o.id}/${name}`, body);
  const shown = orders.filter((o) => columnOf(o.status) === column);
  const count = (c: Column) => orders.filter((o) => columnOf(o.status) === c).length;
  const cashToday = orders.filter((o) => o.paid_at).reduce((s, o) => s + o.grand_total_mru, 0);

  return (
    <section className="caisse">
      <div className="caisse-bar">
        <div className="seg3" role="tablist">
          {(["todo", "doing", "done"] as Column[]).map((c) => (
            <button key={c} type="button" role="tab" aria-selected={column === c} onClick={() => setColumn(c)}>
              {c === "todo" ? "À accepter" : c === "doing" ? "En cours" : "Terminées"} ({count(c)})
            </button>
          ))}
        </div>
        <div className="caisse-tools">
          {!alerts && <button type="button" className="ghost" onClick={enableAlerts}>Activer son et notifications</button>}
          <button type="button" className="primary" onClick={() => setCounter((v) => !v)}>Vente au comptoir</button>
        </div>
        <p className="muted">Encaissé aujourd&apos;hui : <b>{cashToday} MRU</b></p>
      </div>

      {msg && <p className={msg.bad ? "alert bad" : "alert"} role="status">{msg.text}</p>}
      {counter && <CounterForm products={products} busy={busy} onSubmit={async (b) => { if (await post("/api/caisse/orders", b)) setCounter(false); }} />}
      {shown.length === 0 && <p className="muted">Aucune commande ici pour l&apos;instant.</p>}

      <ul className="orders">
        {shown.map((o) => {
          const tel = telLink(o.phone);
          return (
            <li key={o.id} className={`order st-${o.status}`}>
              <div className="order-head">
                <b>{o.number}</b>
                <span className="pill">{STATUS_LABEL[o.status]}</span>
                <span className="muted">{hhmm(o.created_at)}{o.source === "comptoir" ? " · comptoir" : ""}</span>
              </div>
              <ul className="lines">
                {o.lines.map((l) => <li key={l.product_id}>{l.quantity} × {names.get(l.product_id) ?? l.product_id}</li>)}
              </ul>
              <div className="order-info">
                <span><b>{o.customer_name}</b>{tel && <> · <a href={tel}>{o.phone}</a></>}</span>
                <span>{o.fulfilment === "livraison" ? `Livraison · ${o.landmark ?? ""}` : "À emporter"}</span>
                {o.note && <span>Remarque : {o.note}</span>}
                {o.pay_pref && !o.paid_at && <span>Paiement prévu : {PAY_LABEL[o.pay_pref]}</span>}
                {o.ready_at && <span>Prête vers {hhmm(o.ready_at)}</span>}
                {o.customer_called_at && <span>Client appelé à {hhmm(o.customer_called_at)}</span>}
                {o.closed_reason && <span>Motif : {o.closed_reason}</span>}
                <span>
                  Total <b>{o.grand_total_mru} MRU</b>
                  {o.delivery_fee_mru > 0 ? ` (dont livraison ${o.delivery_fee_mru})` : ""}
                  {o.paid_at ? ` · encaissé (${PAY_LABEL[o.paid_method as PaymentMethod]})` : " · non encaissé"}
                </span>
              </div>

              <div className="order-actions">
                {actionsFor(o, me.role).map((a) => {
                  switch (a.kind) {
                    case "accept": return <button key="accept" className="primary" disabled={busy} onClick={() => setPanel({ id: o.id, mode: "accept" })}>Accepter</button>;
                    case "advance": return <button key="adv" className="primary" disabled={busy || !!a.blocked} title={a.blocked} onClick={() => act(o, "status", { status: a.to })}>{a.label}</button>;
                    case "called": return <button key="called" className="ghost" disabled={busy} onClick={() => act(o, "called")}>Client appelé</button>;
                    case "pay": return <button key="pay" className="ghost" disabled={busy} onClick={() => setPanel({ id: o.id, mode: "pay" })}>Encaisser</button>;
                    case "refuse": return <button key="refuse" className="ghost danger" disabled={busy} onClick={() => setPanel({ id: o.id, mode: "refuse" })}>Refuser</button>;
                    case "cancel": return <button key="cancel" className="ghost danger" disabled={busy} onClick={() => setPanel({ id: o.id, mode: "cancel" })}>Annuler</button>;
                  }
                })}
              </div>

              {panel?.id === o.id && panel.mode === "accept" && <AcceptForm order={o} busy={busy} onSubmit={(b) => act(o, "accept", b)} />}
              {panel?.id === o.id && panel.mode === "pay" && (
                <div className="chips">
                  {PAYS.map((m) => <button key={m} className="opt" disabled={busy} onClick={() => act(o, "pay", { method: m })}>{PAY_LABEL[m]}</button>)}
                </div>
              )}
              {panel?.id === o.id && (panel.mode === "refuse" || panel.mode === "cancel") && (
                <ReasonForm label={panel.mode === "refuse" ? "Refuser" : "Annuler"} busy={busy} onSubmit={(reason) => act(o, panel.mode, { reason })} />
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function AcceptForm({ order, busy, onSubmit }: { order: CaisseOrder; busy: boolean; onSubmit: (b: object) => void }) {
  const [delay, setDelay] = useState<number>(15);
  const [fee, setFee] = useState("");
  const delivery = order.fulfilment === "livraison";
  const feeValue = parseFee(fee);
  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit(delivery ? { ready_in_min: delay, delivery_fee_mru: feeValue } : { ready_in_min: delay });
  }
  return (
    <form className="panel" onSubmit={submit}>
      <div className="chips">
        {DELAYS.map((d) => <button key={d} type="button" className="opt" aria-checked={delay === d} role="radio" onClick={() => setDelay(d)}>{d} min</button>)}
      </div>
      {delivery && (
        <div className="field">
          <label htmlFor={`fee-${order.id}`}>Frais de livraison (MRU)</label>
          <input id={`fee-${order.id}`} inputMode="numeric" value={fee} onChange={(e) => setFee(e.target.value)} />
        </div>
      )}
      <button className="primary" type="submit" disabled={busy || (delivery && feeValue === null)}>Confirmer l&apos;acceptation</button>
    </form>
  );
}

function ReasonForm({ label, busy, onSubmit }: { label: string; busy: boolean; onSubmit: (r: string) => void }) {
  const [reason, setReason] = useState("");
  return (
    <form className="panel" onSubmit={(e) => { e.preventDefault(); onSubmit(reason.trim()); }}>
      <div className="field">
        <label>Motif (visible par le client)</label>
        <input value={reason} maxLength={160} onChange={(e) => setReason(e.target.value)} placeholder="Ex. rupture d'avocats" />
      </div>
      <button className="primary danger" type="submit" disabled={busy || reason.trim().length < 3}>{label} la commande</button>
    </form>
  );
}

function CounterForm({ products, busy, onSubmit }: { products: Product[]; busy: boolean; onSubmit: (b: object) => void }) {
  const [qty, setQty] = useState<Record<string, number>>({});
  const [name, setName] = useState("");
  const [paid, setPaid] = useState<PaymentMethod | "">("cash");
  const items = Object.entries(qty).filter(([, q]) => q > 0).map(([product_id, quantity]) => ({ product_id, quantity }));
  const estimate = items.reduce((s, i) => s + (products.find((p) => p.id === i.product_id)?.price_mru ?? 0) * i.quantity, 0);
  const change = (id: string, d: number) => setQty((q) => ({ ...q, [id]: Math.min(20, Math.max(0, (q[id] ?? 0) + d)) }));
  return (
    <form className="track panel" onSubmit={(e) => {
      e.preventDefault();
      onSubmit({ items, ...(name.trim() ? { customer_name: name.trim() } : {}), ...(paid ? { paid_method: paid } : {}) });
    }}>
      <h2>Vente au comptoir</h2>
      <ul className="counter">
        {products.map((p) => (
          <li key={p.id}>
            <span>{p.name_fr} <small className="muted">{p.price_mru} MRU</small></span>
            <span className="stepper">
              <button type="button" aria-label={`Retirer un ${p.name_fr}`} onClick={() => change(p.id, -1)}>−</button>
              <output>{qty[p.id] ?? 0}</output>
              <button type="button" aria-label={`Ajouter un ${p.name_fr}`} onClick={() => change(p.id, 1)}>+</button>
            </span>
          </li>
        ))}
      </ul>
      <div className="field">
        <label htmlFor="counter-name">Prénom (facultatif)</label>
        <input id="counter-name" maxLength={40} value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="chips">
        {PAYS.map((m) => <button key={m} type="button" className="opt" role="radio" aria-checked={paid === m} onClick={() => setPaid(m)}>{PAY_LABEL[m]}</button>)}
        <button type="button" className="opt" role="radio" aria-checked={paid === ""} onClick={() => setPaid("")}>Plus tard</button>
      </div>
      <button className="primary" type="submit" disabled={busy || items.length === 0}>Enregistrer · ≈ {estimate} MRU</button>
    </form>
  );
}
