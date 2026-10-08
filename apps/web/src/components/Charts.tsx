import type { ReactNode } from "react";

/**
 * Graphiques du pilotage (v1.1, réunion 5) : SVG dessiné par le serveur, sans bibliothèque ni
 * script. La CSP interdit les styles en ligne : positions en attributs SVG, couleurs en classes.
 */
export type Point = { label: string; value: number };

const W = 640, H = 220, L = 56, R = 12, T = 14, B = 30;

function scale(max: number): { top: number; ticks: number[] } {
  if (max <= 0) return { top: 1, ticks: [0] };
  const raw = max / 4;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= raw) ?? raw;
  const top = Math.ceil(max / step) * step;
  return { top, ticks: Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step) };
}

const short = (n: number) => (n >= 10_000 ? `${Math.round(n / 1000)} k` : n.toLocaleString("fr-FR").replace(/ | /g, " "));

function Frame({ max, title, children }: { max: number; title: string; children: (y: (v: number) => number) => ReactNode }) {
  const { top, ticks } = scale(max);
  const y = (v: number) => T + (H - T - B) * (1 - v / top);
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
      {ticks.map((t) => (
        <g key={t}>
          <line className="grid" x1={L} x2={W - R} y1={y(t)} y2={y(t)} />
          <text className="tick" x={L - 8} y={y(t) + 4} textAnchor="end">{short(t)}</text>
        </g>
      ))}
      {children(y)}
    </svg>
  );
}

/** Chiffre d'affaires par jour : aire et ligne, un point par jour. */
export function AreaChart({ points, title }: { points: Point[]; title: string }) {
  const max = Math.max(0, ...points.map((p) => p.value));
  const n = points.length;
  const x = (i: number) => (n <= 1 ? (L + W - R) / 2 : L + ((W - R - L) * i) / (n - 1));
  const every = Math.max(1, Math.ceil(n / 8));
  return (
    <Frame max={max} title={title}>
      {(y) => {
        const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`).join("");
        return (
          <>
            {n > 1 && <path className="area" d={`${line}L${x(n - 1)} ${y(0)}L${x(0)} ${y(0)}Z`} />}
            {n > 1 && <path className="line" d={line} />}
            {points.map((p, i) => (
              <g key={p.label + i}>
                <circle className="dot" cx={x(i)} cy={y(p.value)} r={n > 40 ? 2 : 3.5}><title>{`${p.label} : ${short(p.value)} MRU`}</title></circle>
                {i % every === 0 && <text className="tick" x={x(i)} y={H - 10} textAnchor="middle">{p.label}</text>}
              </g>
            ))}
          </>
        );
      }}
    </Frame>
  );
}

/** Commandes par jour : une colonne par jour. */
export function ColumnChart({ points, title }: { points: Point[]; title: string }) {
  const max = Math.max(0, ...points.map((p) => p.value));
  const n = Math.max(points.length, 1);
  const slot = (W - R - L) / n;
  const bw = Math.max(2, Math.min(28, slot * 0.7));
  const every = Math.max(1, Math.ceil(n / 8));
  return (
    <Frame max={max} title={title}>
      {(y) => points.map((p, i) => (
        <g key={p.label + i}>
          <rect className="col" x={L + slot * i + (slot - bw) / 2} y={y(p.value)} width={bw} height={Math.max(0, y(0) - y(p.value))} rx={3}>
            <title>{`${p.label} : ${p.value} commande(s)`}</title>
          </rect>
          {i % every === 0 && <text className="tick" x={L + slot * i + slot / 2} y={H - 10} textAnchor="middle">{p.label}</text>}
        </g>
      ))}
    </Frame>
  );
}
