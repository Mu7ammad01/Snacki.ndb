"use client";

import { useEffect, useMemo, useState } from "react";

import { Back, Close, Leaf, Minus, Plus, Wa } from "@/components/Icons";
import { type Cart, cartCount, estimateTotal, sanitizeCart, setQty, toItems } from "@/lib/cart";
import { CONTACT, PAYMENTS, T, ZONES, fmt } from "@/lib/i18n";
import { applyLang, store } from "@/lib/storage";
import { trackingPath } from "@/lib/token";
import type { Category, Lang, OrderCreated, OrderRequest, PaymentMethod, Product } from "@/lib/types";
import { type FieldError, type InfoForm, normalizePhone, oneLine, validateInfo } from "@/lib/validate";
import { contactMessage, waLink } from "@/lib/whatsapp";

type Step = null | "cart" | "info" | "done";
interface Form extends InfoForm { pay: string; note: string }

const EMPTY_FORM: Form = { name: "", phone: "", mode: "emporter", zone: "ndb", landmark: "", pay: "cash", note: "" };

/** Photo servie par le site lui-même : on n'accepte qu'un nom de fichier connu, jamais une URL. */
export const safePhoto = (photo: string | null) => (photo && /^img\/[a-z-]+\.jpg$/.test(photo) ? "/" + photo : null);

export default function Shop({ products }: { products: Product[] | null }) {
  const list = useMemo(() => products ?? [], [products]);
  const byId = useMemo(() => new Map(list.map((p) => [p.id, p])), [list]);
  const [lang, setLang] = useState<Lang>("fr");
  const [cat, setCat] = useState<"all" | Category>("all");
  const [cart, setCart] = useState<Cart>({});
  const [step, setStep] = useState<Step>(null);
  const [form, setForm] = useState<Form>(EMPTY_FORM);
  const [touched, setTouched] = useState<Partial<Record<FieldError, boolean>>>({});
  const [order, setOrder] = useState<OrderCreated | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t = T[lang];

  // Préférences relues après l'affichage (le serveur ne connaît pas le localStorage).
  useEffect(() => {
    setLang(store.get<Lang>("lang", "fr") === "ar" ? "ar" : "fr");
    setCart(sanitizeCart(store.get("cart", {}), new Set(byId.keys())));
    const saved = store.get<Partial<Form>>("client", {});
    setForm((f) => ({ ...f, name: String(saved.name ?? ""), phone: String(saved.phone ?? ""), zone: String(saved.zone ?? "ndb"), landmark: String(saved.landmark ?? "") }));
  }, [byId]);
  useEffect(() => { applyLang(lang); store.set("lang", lang); }, [lang]);
  useEffect(() => { store.set("cart", cart); }, [cart]);
  useEffect(() => { document.body.style.overflow = step ? "hidden" : ""; }, [step]);

  const pname = (p: Product) => (lang === "ar" ? p.name_ar : p.name_fr);
  const errors = validateInfo(form);
  const showErr = (k: FieldError) => touched[k] && errors.includes(k);
  const update = (patch: Partial<Form>) => {
    const next = { ...form, ...patch };
    setForm(next);
    store.set("client", { name: next.name, phone: next.phone, zone: next.zone, landmark: next.landmark });
  };

  async function submit() {
    if (errors.length) { setTouched({ name: true, phone: true, landmark: true }); return; }
    const zone = ZONES.find((z) => z.id === form.zone) ?? ZONES[0];
    const body: OrderRequest = {
      customer_name: oneLine(form.name),
      phone: normalizePhone(form.phone),
      fulfilment: form.mode,
      items: toItems(cart),
      ...(form.mode === "livraison" ? { landmark: `${zone.fr} — ${oneLine(form.landmark)}` } : {}),
      // Ces informations allaient dans le message WhatsApp ; elles arrivent maintenant en caisse.
      ...(PAYMENTS.some((p) => p.id === form.pay) ? { pay_pref: form.pay as PaymentMethod } : {}),
      ...(oneLine(form.note) ? { note: oneLine(form.note).slice(0, 200) } : {}),
    };
    setSending(true); setError(null);
    try {
      const r = await fetch("/api/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await r.json();
      if (r.status === 201) { setOrder(data as OrderCreated); setStep("done"); return; }
      if (r.status === 429) setError(t.errRate(Number(r.headers.get("retry-after") ?? 60)));
      else if (r.status === 422 && String(data?.detail ?? "").startsWith("Produit indisponible")) setError(t.errUnavailable);
      else if (r.status === 422) setError(t.errInvalid);
      else setError(t.errNetwork);
    } catch {
      setError(t.errNetwork);
    } finally {
      setSending(false);
    }
  }

  function newOrder() {
    setCart({}); setOrder(null); setTouched({}); setError(null);
    setForm((f) => ({ ...f, note: "" })); setStep(null); window.scrollTo({ top: 0 });
  }


  const Qty = ({ p, compact }: { p: Product; compact?: boolean }) => {
    const q = cart[p.id] ?? 0;
    if (!q && !compact)
      return (
        <button type="button" className="add" aria-label={`${t.add} — ${pname(p)}`} onClick={() => setCart((c) => setQty(c, p.id, 1))}><Plus /></button>
      );
    return (
      <div className="stepper" role="group" aria-label={pname(p)}>
        <button type="button" aria-label={`${t.less} — ${pname(p)}`} onClick={() => setCart((c) => setQty(c, p.id, q - 1))}><Minus /></button>
        <output aria-live="polite">{q}</output>
        <button type="button" aria-label={`${t.more} — ${pname(p)}`} onClick={() => setCart((c) => setQty(c, p.id, q + 1))}><Plus /></button>
      </div>
    );
  };

  const Photo = ({ p, cls }: { p: Product; cls: string }) => {
    const src = safePhoto(p.photo);
    return src ? <img className={cls} src={src} alt={pname(p)} loading="lazy" /> : <div className={`${cls} empty`} aria-hidden="true">{pname(p).charAt(0)}</div>;
  };

  const n = cartCount(cart);
  const estimate = estimateTotal(cart, byId);

  return (
    <>
      <div className="app">
        <header className="top">
          <img className="logo" src="/img/logo.jpg" alt="Snacki — عصائر و ديسيرات" width={118} height={79} />
          <div className="lang" role="group" aria-label="Langue / اللغة">
            <button type="button" aria-pressed={lang === "fr"} onClick={() => setLang("fr")}>FR</button>
            <button type="button" aria-pressed={lang === "ar"} onClick={() => setLang("ar")}>عربي</button>
          </div>
        </header>

        <section className="intro" aria-labelledby="intro-t">
          <h1 id="intro-t">{t.introTitle}</h1>
          <p>{t.introText}</p>
          <div className="steps"><span>{t.s1}</span><span>{t.s2}</span><span>{t.s3}</span></div>
        </section>

        {products === null ? (
          <p className="alert bad" role="alert">{t.menuDown}</p>
        ) : (
          <>
            <nav className="tabs" role="tablist">
              {(["all", "delices", "jus"] as const).map((c) => (
                <button key={c} type="button" role="tab" className="tab" aria-selected={cat === c} onClick={() => setCat(c)}>{t[c]}</button>
              ))}
            </nav>
            <main>
              {(["delices", "jus"] as const).filter((c) => cat === "all" || cat === c).map((c) => (
                <section key={c} className="section" aria-labelledby={`sec-${c}`}>
                  <h2 className="brush" id={`sec-${c}`}><span><Leaf /></span><span>{t[c]}</span></h2>
                  <div className="grid">
                    {list.filter((p) => p.category === c).map((p) => (
                      <article key={p.id} className="card">
                        <Photo p={p} cls="ph" />
                        {p.badge ? <span className={`badge${p.badge === "pop" ? " pop" : ""}`}>{t[p.badge]}</span> : null}
                        <div className="cbody">
                          <h3 className="name">{pname(p)}</h3>
                          <p className="alt" lang={lang === "fr" ? "ar" : "fr"} dir={lang === "fr" ? "rtl" : "ltr"}>{lang === "fr" ? p.name_ar : p.name_fr}</p>
                          <p className="desc">{lang === "fr" ? p.description_fr : p.description_ar}</p>
                          <div className="row">
                            <span className="price">{fmt(p.price_mru)}<small>MRU</small></span>
                            <Qty p={p} />
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              ))}
            </main>
          </>
        )}

        <footer className="contact">
          <div>{t.waLabel} <b dir="ltr">{CONTACT.whatsappDisplay}</b> · {t.callLabel} <b dir="ltr">{CONTACT.call}</b></div>
          <div>TikTok <b dir="ltr">@snackifood</b></div>
          <div className="pay" aria-label={t.payment}>{PAYMENTS.map((p) => <span key={p.id}>{p[lang]}</span>)}</div>
        </footer>
      </div>

      <div className="bar" hidden={n === 0 || step !== null}>
        <button type="button" onClick={() => setStep("cart")}>
          <span className="count">{n}</span>
          <span className="lbl">{t.seeCart}</span>
          <span className="tot">{fmt(estimate)} MRU</span>
        </button>
      </div>

      {step && (
        <div className="scrim" onClick={(e) => { if (e.target === e.currentTarget && step !== "done") setStep(null); }}>
          <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
            <div className="shead">
              {step === "info" ? <button type="button" className="icon-btn" aria-label={t.back} onClick={() => setStep("cart")}><Back /></button> : null}
              <h2 id="sheet-title">{step === "cart" ? t.cartTitle : step === "info" ? t.infoTitle : t.doneTitle}</h2>
              <button type="button" className="icon-btn" aria-label={t.close} onClick={() => (step === "done" ? newOrder() : setStep(null))}><Close /></button>
            </div>
            <div className="progress" aria-hidden="true">
              {[1, 2, 3].map((i) => <i key={i} className={i <= { cart: 1, info: 2, done: 3 }[step] ? "on" : ""} />)}
            </div>

            {step === "cart" && (
              <>
                <div className="sbody">
                  {n === 0 ? <p className="muted">{t.emptyCart}</p> : Object.entries(cart).map(([id, q]) => {
                    const p = byId.get(id);
                    if (!p) return null;
                    return (
                      <div className="line" key={id}>
                        <Photo p={p} cls="thumb" />
                        <div><div className="n">{pname(p)}</div><div className="s">{q} × {fmt(p.price_mru)} = {fmt(q * p.price_mru)} MRU</div></div>
                        <Qty p={p} compact />
                      </div>
                    );
                  })}
                </div>
                {n > 0 && (
                  <div className="sfoot">
                    <div className="sum big"><span>{t.estimate}</span><span>{fmt(estimate)} MRU</span></div>
                    <button type="button" className="primary" onClick={() => setStep("info")}>{t.next}</button>
                  </div>
                )}
              </>
            )}

            {step === "info" && (
              <>
                <div className="sbody">
                  <div className="field">
                    <label htmlFor="f-name">{t.name}</label>
                    <input id="f-name" autoComplete="given-name" placeholder={t.namePh} value={form.name} maxLength={40} aria-invalid={!!showErr("name")}
                      onChange={(e) => update({ name: e.target.value })} onBlur={() => setTouched((x) => ({ ...x, name: true }))} />
                    <div className="err">{showErr("name") ? t.nameErr : ""}</div>
                  </div>
                  <div className="field">
                    <label htmlFor="f-phone">{t.phone}</label>
                    <div className={`phone${showErr("phone") ? " bad" : ""}`}>
                      <span>+222</span>
                      <input id="f-phone" type="tel" inputMode="numeric" autoComplete="tel-national" placeholder="37 93 94 09" value={form.phone} maxLength={11}
                        onChange={(e) => update({ phone: e.target.value })} onBlur={() => setTouched((x) => ({ ...x, phone: true }))} />
                    </div>
                    <div className="err">{showErr("phone") ? t.phoneErr : ""}</div>
                  </div>
                  <div className="field">
                    <div className="lab" id="l-mode">{t.mode}</div>
                    <div className="seg" role="radiogroup" aria-labelledby="l-mode">
                      <button type="button" role="radio" className="opt" aria-checked={form.mode === "emporter"} onClick={() => update({ mode: "emporter" })}><span>{t.pickup}<small>{t.pickupSub}</small></span></button>
                      <button type="button" role="radio" className="opt" aria-checked={form.mode === "livraison"} onClick={() => update({ mode: "livraison" })}><span>{t.delivery}<small>{t.deliverySub}</small></span></button>
                    </div>
                  </div>
                  {form.mode === "livraison" && (
                    <>
                      <div className="field">
                        <label htmlFor="f-zone">{t.zone}</label>
                        <select id="f-zone" value={form.zone} onChange={(e) => update({ zone: e.target.value })}>
                          {ZONES.map((z) => <option key={z.id} value={z.id}>{z[lang]}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor="f-landmark">{t.landmark}</label>
                        <input id="f-landmark" placeholder={t.landmarkPh} value={form.landmark} maxLength={100} aria-invalid={!!showErr("landmark")}
                          onChange={(e) => update({ landmark: e.target.value })} onBlur={() => setTouched((x) => ({ ...x, landmark: true }))} />
                        <div className="err">{showErr("landmark") ? t.landmarkErr : ""}</div>
                      </div>
                      <p className="note-box fee">{t.feeNote}</p>
                    </>
                  )}
                  <div className="field">
                    <div className="lab" id="l-pay">{t.payment}</div>
                    <div className="chips" role="radiogroup" aria-labelledby="l-pay">
                      {PAYMENTS.map((p) => (
                        <button key={p.id} type="button" role="radio" className="opt" aria-checked={form.pay === p.id} onClick={() => update({ pay: p.id })}><span>{p[lang]}</span></button>
                      ))}
                    </div>
                  </div>
                  <div className="field">
                    <label htmlFor="f-note">{t.note}</label>
                    <textarea id="f-note" rows={2} maxLength={200} placeholder={t.notePh} value={form.note} onChange={(e) => update({ note: e.target.value })} />
                  </div>
                  {error ? <p className="alert bad" role="alert">{error}</p> : null}
                </div>
                <div className="sfoot">
                  <div className="sum"><span className="muted">{t.items(n)}</span><strong className="sum-v">≈ {fmt(estimate)} MRU</strong></div>
                  <button type="button" className="primary" disabled={sending} onClick={submit}>{sending ? t.sending : t.validate}</button>
                </div>
              </>
            )}

            {step === "done" && order && (
              <>
                <div className="sbody">
                  <div className="done-num"><div className="k">{t.orderNo}</div><div className="v">{order.number}</div></div>
                  <div className="sum big"><span>{t.total}</span><span>{fmt(order.total_mru)} MRU</span></div>
                  <p className="alert">{t.sentToShop}</p>
                  <p className="muted gap6">{t.after}</p>
                </div>
                <div className="sfoot">
                  <a className="primary" href={trackingPath(order.tracking_token)}>{t.track}</a>
                  <a className="contact-wa" href={waLink(contactMessage(lang, order.number))} target="_blank" rel="noopener noreferrer"><Wa />{t.contactWa}</a>
                  <button type="button" className="ghost" onClick={newOrder}>{t.newOrder}</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
