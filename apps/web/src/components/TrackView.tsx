"use client";

import { useEffect, useState } from "react";

import { T, fmt } from "@/lib/i18n";
import { applyLang, store } from "@/lib/storage";
import { tokenFromHash } from "@/lib/token";
import type { Lang, OrderStatus, OrderTrack } from "@/lib/types";

const STEPS: OrderStatus[] = ["recue", "en_preparation", "prete", "livree"];
const REFRESH_MS = 15_000; // le suivi en direct (SSE) arrive à J7

export default function TrackView() {
  const [lang, setLang] = useState<Lang>("fr");
  const [order, setOrder] = useState<OrderTrack | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "notfound" | "error">("loading");
  const t = T[lang];

  useEffect(() => {
    const l = store.get<Lang>("lang", "fr") === "ar" ? "ar" : "fr";
    setLang(l); applyLang(l);
    const token = tokenFromHash(window.location.hash);
    if (!token) { setState("notfound"); return; }
    let stop = false;
    async function load() {
      try {
        // Le jeton part dans un en-tête, jamais dans l'URL (T03).
        const r = await fetch("/api/track", { headers: { "X-Tracking-Token": token as string }, cache: "no-store" });
        if (stop) return;
        if (r.ok) { setOrder((await r.json()) as OrderTrack); setState("ok"); }
        else setState(r.status === 404 ? "notfound" : "error");
      } catch { if (!stop) setState("error"); }
    }
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => { stop = true; clearInterval(id); };
  }, []);

  const reached = order ? STEPS.indexOf(order.status) : -1;
  return (
    <div className="app">
      <section className="track" aria-live="polite">
        <h1>{t.trackTitle}</h1>
        {state === "loading" && <p className="muted">{t.trackLoading}</p>}
        {state === "notfound" && <p className="alert bad">{t.trackNotFound}</p>}
        {state === "error" && <p className="alert bad">{t.errNetwork}</p>}
        {state === "ok" && order && (
          <>
            <div className="done-num"><div className="k">{t.orderNo}</div><div className="v">{order.number}</div></div>
            <ol className="timeline">
              {order.status === "annulee"
                ? <li className="cancel">{t.status.annulee}</li>
                : STEPS.filter((s) => s !== "livree" || order.fulfilment === "livraison").map((s, i) => (
                    <li key={s} className={i <= reached ? "done" : ""}>{t.status[s]}</li>
                  ))}
            </ol>
            <div className="sum big"><span>{t.total}</span><span>{fmt(order.total_mru)} MRU</span></div>
            <p className="muted gap10">{t.trackRefresh}</p>
          </>
        )}
        <p className="gap10"><a className="ghost" href="/">{t.backToMenu}</a></p>
      </section>
    </div>
  );
}
