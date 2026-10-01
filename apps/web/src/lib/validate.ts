/**
 * Validation côté navigateur : une aide à la saisie, pas une protection.
 * L'API refait toutes ces vérifications (ASVS V2.2.2) ; les règles sont les mêmes.
 */

export interface InfoForm {
  name: string;
  phone: string;
  mode: "emporter" | "livraison";
  zone: string;
  landmark: string;
}

export type FieldError = "name" | "phone" | "landmark";

export function normalizePhone(raw: string): string {
  let digits = raw.replace(/[\s.-]/g, "");
  for (const prefix of ["+222", "00222"]) if (digits.startsWith(prefix)) digits = digits.slice(prefix.length);
  return digits;
}

export function validateInfo(f: InfoForm): FieldError[] {
  const errors: FieldError[] = [];
  if (f.name.trim().length < 2 || f.name.trim().length > 40) errors.push("name");
  if (!/^[234]\d{7}$/.test(normalizePhone(f.phone))) errors.push("phone");
  if (f.mode === "livraison" && (f.landmark.trim().length < 3 || f.landmark.trim().length > 100))
    errors.push("landmark");
  return errors;
}

/** Supprime retours à la ligne et caractères de contrôle d'un texte libre. */
export const oneLine = (s: string) => s.replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s{2,}/g, " ").trim();
