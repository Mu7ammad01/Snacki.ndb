/**
 * Pilotage (J8) : période demandée et mise en forme des chiffres, testées sans serveur.
 * Les chiffres eux-mêmes sont calculés par l'API ; le web ne fait que les afficher.
 */
const ISO = /^\d{4}-\d{2}-\d{2}$/;

export type Period = { start: string; end: string };

const iso = (d: Date) => d.toISOString().slice(0, 10);

function addDays(day: string, n: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return iso(d);
}

/** Date AAAA-MM-JJ réelle, sinon null (« 2026-02-30 » est refusé). */
export function validDay(value: unknown): string | null {
  if (typeof value !== "string" || !ISO.test(value)) return null;
  return iso(new Date(`${value}T00:00:00Z`)) === value ? value : null;
}

/** Période lue dans l'URL ; valeurs absentes ou invalides : les 30 derniers jours. */
export function periodFrom(params: { start?: unknown; end?: unknown }, today: string): Period {
  const end = validDay(params.end) ?? today;
  const start = validDay(params.start) ?? addDays(end, -29);
  return start <= end ? { start, end } : { start: end, end };
}

export function presets(today: string): { label: string; period: Period }[] {
  return [
    { label: "Aujourd'hui", period: { start: today, end: today } },
    { label: "7 jours", period: { start: addDays(today, -6), end: today } },
    { label: "30 jours", period: { start: addDays(today, -29), end: today } },
    { label: "Ce mois", period: { start: `${today.slice(0, 8)}01`, end: today } },
  ];
}

export const mru = (n: number) => `${n.toLocaleString("fr-FR").replace(/ | /g, " ")} MRU`;

/** Largeur d'une barre en % de la plus grande valeur (au moins 2 % pour rester visible). */
export function share(value: number, max: number): number {
  if (max <= 0 || value <= 0) return 0;
  return Math.max(2, Math.round((value / max) * 100));
}

export const shortDay = (day: string) => `${day.slice(8, 10)}/${day.slice(5, 7)}`;
