"use client";

/** localStorage peut être absent ou bloqué (navigation privée) : on ne plante jamais. */
export const store = {
  get<T>(key: string, fallback: T): T {
    try {
      const v = localStorage.getItem("snacki_" + key);
      return v ? (JSON.parse(v) as T) : fallback;
    } catch {
      return fallback;
    }
  },
  set(key: string, value: unknown) {
    try {
      localStorage.setItem("snacki_" + key, JSON.stringify(value));
    } catch {
      /* stockage indisponible : l'app fonctionne sans */
    }
  },
};

export function applyLang(lang: "fr" | "ar") {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
}
