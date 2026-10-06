"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import {
  DELAYS,
  PAY_LABEL,
  STATUS_LABEL,
  actionsFor,
  cardFrom,
  columnOf,
  hhmm,
  newArrivals,
  parseFee,
  telLink,
  type Column,
} from "@/lib/caisse";
import QrScanner, { canScan } from "@/components/QrScanner";
import type { StaffMe } from "@/lib/staff";
import type { AssistantResult, CaisseOrder, LoyaltyCard, PaymentMethod, Product } from "@/lib/types";

const REFRESH_MS = 5_000;
const PAYS = Object.keys(PAY_LABEL) as PaymentMethod[];
type Panel = null | { id: number; mode: "accept" | "refuse" | "cancel" | "pay" | "stamp" | "reward" };

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
  const [fidelity, setFidelity] = useState(false);
  const [helper, setHelper] = useState(false);
  const [preset, setPreset] = useState<{ key: number; qty: Record<string, number> }>({ key: 0, qty: {} });
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
          <button type="button" className="ghost" onClick={() => setFidelity((v) => !v)}>Carte fidélité</button>
          <button type="button" className="ghost" onClick={() => setHelper((v) => !v)}>Message WhatsApp</button>
        </div>
        <p className="muted">Encaissé aujourd&apos;hui : <b>{cashToday} MRU</b></p>
      </div>

      {msg && <p className={msg.bad ? "alert bad" : "alert"} role="status">{msg.text}</p>}
      {helper && <AssistantTool onUse={(qty) => { setPreset((p) => ({ key: p.key + 1, qty })); setHelper(false); setCounter(true); }} />}
      {counter && <CounterForm key={preset.key} initial={preset.qty} products={products} busy={busy} onSubmit={async (b) => { if (await post("/api/caisse/orders", b)) { setCounter(false); setPreset((p) => ({ key: p.key + 1, qty: {} })); } }} />}
      {fidelity && <FidelityTool manager={me.role !== "caissier"} />}
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
                {(o.discount_mru ?? 0) > 0 && <span><b>Cadeau fidélité : − {o.discount_mru} MRU</b></span>}
                {o.loyalty_card_id && !o.discount_mru && <span>Tampon fidélité donné</span>}
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
                    case "stamp": return <button key="stamp" className="ghost" disabled={busy} onClick={() => setPanel({ id: o.id, mode: "stamp" })}>Tampon fidélité</button>;
                    case "reward": return <button key="reward" className="ghost" disabled={busy} onClick={() => setPanel({ id: o.id, mode: "reward" })}>Cadeau fidélité</button>;
                  }
                })}
              </div>

              {panel?.id === o.id && panel.mode === "accept" && <AcceptForm order={o} busy={busy} onSubmit={(b) => act(o, "accept", b)} />}
              {panel?.id === o.id && panel.mode === "pay" && (
                <div className="chips">
                  {PAYS.map((m) => <button key={m} className="opt" disabled={busy} onClick={() => act(o, "pay", { method: m })}>{PAY_LABEL[m]}</button>)}
                </div>
              )}
              {panel?.id === o.id && (panel.mode === "stamp" || panel.mode === "reward") && (
                <CardForm withPhone={panel.mode === "stamp"} label={panel.mode === "stamp" ? "Donner le tampon" : "Offrir (100 MRU au plus)"} busy={busy}
                  onSubmit={(b) => act(o, panel.mode === "stamp" ? "loyalty" : "reward", b)} />
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

function CounterForm({ products, busy, onSubmit, initial = {} }: { products: Product[]; busy: boolean; onSubmit: (b: object) => void; initial?: Record<string, number> }) {
  const [qty, setQty] = useState<Record<string, number>>(initial);
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

/** Numéro de carte : lu par la caméra (QR) ou saisi ; téléphone facultatif au premier tampon. */
function CardForm({ withPhone, label, busy, onSubmit }: { withPhone: boolean; label: string; busy: boolean; onSubmit: (b: object) => void }) {
  const [code, setCode] = useState("");
  const [phone, setPhone] = useState("");
  const [scan, setScan] = useState(false);
  const card = cardFrom(code);
  return (
    <form className="panel" onSubmit={(e) => { e.preventDefault(); if (card) onSubmit(withPhone && phone ? { code: card, phone } : { code: card }); }}>
      {scan && <QrScanner onRead={setCode} onClose={() => setScan(false)} />}
      <div className="field">
        <label>Numéro de la carte</label>
        <input value={code} maxLength={40} autoCapitalize="characters" placeholder="FID-XXXX-XXXX" onChange={(e) => setCode(e.target.value)} />
      </div>
      {canScan() && !scan && <button type="button" className="ghost" onClick={() => setScan(true)}>Scanner le QR</button>}
      {withPhone && (
        <div className="field">
          <label>Téléphone du client (facultatif, pour retrouver une carte perdue)</label>
          <input value={phone} inputMode="tel" maxLength={12} onChange={(e) => setPhone(e.target.value)} />
        </div>
      )}
      <button className="primary" type="submit" disabled={busy || !card}>{label}</button>
    </form>
  );
}

/** Outil fidélité : état d'une carte ; gérante et admin : bloquer, remplacer, retrouver. */
function FidelityTool({ manager }: { manager: boolean }) {
  const [code, setCode] = useState("");
  const [scan, setScan] = useState(false);
  const [info, setInfo] = useState<LoyaltyCard[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [newCode, setNewCode] = useState("");
  const [phone, setPhone] = useState("");
  const card = cardFrom(code);

  async function call(url: string, body: object) {
    setMsg(null);
    try {
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = (await r.json().catch(() => ({}))) as { detail?: unknown };
      if (!r.ok) { setMsg(typeof data.detail === "string" ? data.detail : "Action refusée"); return; }
      setInfo(Array.isArray(data) ? (data as LoyaltyCard[]) : [data as LoyaltyCard]);
    } catch {
      setMsg("Service momentanément indisponible");
    }
  }

  return (
    <section className="track panel">
      <h2>Carte fidélité</h2>
      {scan && <QrScanner onRead={setCode} onClose={() => setScan(false)} />}
      <div className="field">
        <label>Numéro de la carte</label>
        <input value={code} maxLength={40} placeholder="FID-XXXX-XXXX" onChange={(e) => setCode(e.target.value)} />
      </div>
      <div className="caisse-tools">
        {canScan() && <button type="button" className="ghost" onClick={() => setScan(true)}>Scanner le QR</button>}
        <button type="button" className="primary" disabled={!card} onClick={() => card && call("/api/caisse/loyalty", { code: card })}>Voir la carte</button>
      </div>
      {msg && <p className="alert bad" role="status">{msg}</p>}
      {info?.map((c) => (
        <p key={c.card} className="alert">
          <b>{c.card}</b> · {c.status === "blocked" ? "BLOQUÉE" : `${c.progress}/${c.goal} tampons`} · cadeau(x) disponible(s) : {c.rewards_available} · déjà offerts : {c.rewards_taken}{c.phone_linked ? " · téléphone enregistré" : ""}
        </p>
      ))}
      {manager && (
        <>
          <div className="field">
            <label>Motif du blocage (carte perdue, volée, suspecte)</label>
            <input value={reason} maxLength={160} onChange={(e) => setReason(e.target.value)} />
          </div>
          <button type="button" className="ghost danger" disabled={!card || reason.trim().length < 3} onClick={() => card && call("/api/loyalty/block", { code: card, reason: reason.trim() })}>Bloquer la carte</button>
          <div className="field">
            <label>Carte perdue : numéro de la carte neuve qui reprend les tampons</label>
            <input value={newCode} maxLength={40} placeholder="FID-XXXX-XXXX" onChange={(e) => setNewCode(e.target.value)} />
          </div>
          <button type="button" className="ghost" disabled={!card || !cardFrom(newCode)} onClick={() => card && call("/api/loyalty/transfer", { old_code: card, new_code: cardFrom(newCode) })}>Reporter les tampons</button>
          <div className="field">
            <label>Retrouver une carte par le téléphone du client</label>
            <input value={phone} inputMode="tel" maxLength={8} onChange={(e) => setPhone(e.target.value)} />
          </div>
          <button type="button" className="ghost" disabled={!/^[234]\d{7}$/.test(phone)} onClick={() => call("/api/loyalty/search", { phone })}>Rechercher</button>
        </>
      )}
    </section>
  );
}

/**
 * Assistant de commande (J9) : la caissière colle un message WhatsApp, l'API propose des produits
 * et des quantités (prix de la base). Rien n'est créé : la proposition remplit la vente au
 * comptoir, que la caissière vérifie et enregistre elle-même.
 */
function AssistantTool({ onUse }: { onUse: (qty: Record<string, number>) => void }) {
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<AssistantResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function analyse(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await fetch("/api/caisse/assistant", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: message.trim() }),
      });
      if (r.status === 429) setError("Trop de demandes : réessayez dans une minute.");
      else if (!r.ok) setError("Analyse impossible : saisissez la vente à la main.");
      else setResult((await r.json()) as AssistantResult);
    } catch {
      setError("Connexion impossible.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="panel" onSubmit={analyse}>
      <h2>Message WhatsApp</h2>
      <div className="field">
        <label htmlFor="wa-text">Collez le message du client</label>
        <textarea id="wa-text" rows={4} maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} />
      </div>
      <button className="primary" type="submit" disabled={busy || message.trim().length < 3}>{busy ? "Analyse…" : "Analyser"}</button>
      {error && <p className="alert bad" role="status">{error}</p>}
      {result && (
        <div role="status">
          <p className="muted">{result.engine === "gemini" ? "Proposition de l'IA" : "Analyse simple"} : à vérifier avant d&apos;enregistrer.</p>
          <ul>{result.lines.map((l) => <li key={l.product_id}>{l.quantity} × {l.name} · {l.total_mru} MRU</li>)}</ul>
          {result.lines.length > 0 && <p><b>Total ≈ {result.total_mru} MRU</b>{result.fulfilment === "livraison" ? " · livraison demandée" : ""}</p>}
          {result.unknown.length > 0 && <p className="muted">Hors menu : {result.unknown.join(", ")}</p>}
          {result.warnings.map((w) => <p key={w} className="alert bad">{w}</p>)}
          {result.lines.length > 0 && (
            <button type="button" className="primary" onClick={() => onUse(Object.fromEntries(result.lines.map((l) => [l.product_id, l.quantity])))}>
              Remplir la vente au comptoir
            </button>
          )}
        </div>
      )}
    </form>
  );
}
