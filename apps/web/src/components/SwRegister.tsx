"use client";

import { useEffect } from "react";

/** Enregistre le service worker (J11) : installation sur l'écran d'accueil et page hors connexion. */
export default function SwRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      // Sans service worker, l'app marche comme un site normal : rien à signaler au client.
    });
  }, []);
  return null;
}
