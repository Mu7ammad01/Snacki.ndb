import type { Lang } from "@/lib/types";

/**
 * Réunion 5 (demande 5) : sans choix enregistré, l'app suit la langue du téléphone.
 * Arabe (ar, ar-MR…) → arabe ; toute autre langue → français. Un choix fait avec le bouton
 * FR / عربي est gardé et l'emporte ensuite.
 */
export function phoneLang(languages: readonly string[] | undefined): Lang {
  const first = (languages ?? []).find((l) => typeof l === "string" && l.length > 0) ?? "";
  return first.toLowerCase().startsWith("ar") ? "ar" : "fr";
}

export function initialLang(saved: unknown, languages: readonly string[] | undefined): Lang {
  return saved === "ar" || saved === "fr" ? saved : phoneLang(languages);
}
