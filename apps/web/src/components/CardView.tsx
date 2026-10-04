"use client";

import { useEffect, useState } from "react";

import { cardFrom } from "@/lib/caisse";
import type { LoyaltyPublic } from "@/lib/types";

export default function CardView() {
  const [card, setCard] = useState<LoyaltyPublic | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "notfound" | "error">("loading");

  useEffect(() => {
    const code = cardFrom(decodeURIComponent(window.location.hash.slice(1)));
    if (!code) { setState("notfound"); return; }
    fetch("/api/loyalty/status", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) })
      .then(async (r) => {
        if (r.status === 404) { setState("notfound"); return; }
        if (!r.ok) { setState("error"); return; }
        setCard((await r.json()) as LoyaltyPublic);
        setState("ok");
      })
      .catch(() => setState("error"));
  }, []);

  const dots = card ? Array.from({ length: card.goal }, (_, i) => i < card.progress) : [];

  return (
    <main className="app">
      <div className="track">
        <h1>Ma carte fidélité</h1>
        <p className="muted" dir="rtl" lang="ar">بطاقة الوفاء</p>
        {state === "loading" && <p className="muted">Chargement…</p>}
        {state === "notfound" && <p className="alert bad">Carte introuvable. Vérifiez le numéro imprimé sous le QR.</p>}
        {state === "error" && <p className="alert bad">Service momentanément indisponible, réessayez.</p>}
        {card && (
          <>
            <p className="done-num"><span className="v">{card.card}</span></p>
            {card.status === "blocked" ? (
              <p className="alert bad">Cette carte est bloquée. Passez au snack : la gérante vous aidera.</p>
            ) : (
              <>
                <ol className="stamps" aria-label={`${card.progress} tampon(s) sur ${card.goal}`}>
                  {dots.map((on, i) => <li key={i} className={on ? "on" : ""}>{i + 1}</li>)}
                  <li className="gift">Cadeau</li>
                </ol>
                {card.rewards_available > 0 ? (
                  <p className="alert"><b>{card.rewards_available} commande(s) offerte(s) disponible(s)</b> (100 MRU au plus) : montrez votre carte à la caisse.</p>
                ) : (
                  <p className="alert">Encore {card.goal - card.progress} achat(s) avant votre commande offerte.</p>
                )}
              </>
            )}
            <p className="muted">5 achats = 1 commande offerte. Un tampon par commande encaissée, au plus 3 par jour.</p>
          </>
        )}
        <a className="ghost" href="/">Voir le menu</a>
      </div>
    </main>
  );
}
