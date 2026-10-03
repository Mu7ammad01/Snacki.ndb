import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { mru, periodFrom, presets, share, shortDay, validDay } from "@/lib/pilotage";

const TODAY = "2026-10-07";

describe("pilotage · période", () => {
  it("par défaut, les 30 derniers jours", () => {
    expect(periodFrom({}, TODAY)).toEqual({ start: "2026-09-08", end: TODAY });
  });

  it("refuse les dates fausses ou forgées", () => {
    for (const bad of ["2026-02-30", "07/10/2026", "2026-10-07'; DROP TABLE orders; --", 42, ["2026-10-01"]]) {
      expect(validDay(bad)).toBeNull();
    }
    expect(periodFrom({ start: "2026-02-30", end: "x" }, TODAY)).toEqual({ start: "2026-09-08", end: TODAY });
  });

  it("début après la fin : ramené à la fin", () => {
    expect(periodFrom({ start: "2026-10-05", end: "2026-10-01" }, TODAY)).toEqual({ start: "2026-10-01", end: "2026-10-01" });
  });

  it("raccourcis : aujourd'hui, 7 jours, 30 jours, ce mois", () => {
    const p = presets(TODAY).map((x) => x.period.start);
    expect(p).toEqual([TODAY, "2026-10-01", "2026-09-08", "2026-10-01"]);
  });
});

describe("pilotage · affichage", () => {
  it("montants et jours lisibles", () => {
    expect(mru(46310)).toBe("46 310 MRU");
    expect(shortDay("2026-09-02")).toBe("02/09");
  });

  it("barres proportionnelles, jamais invisibles ni négatives", () => {
    expect(share(50, 100)).toBe(50);
    expect(share(1, 1000)).toBe(2);
    expect(share(0, 100)).toBe(0);
    expect(share(5, 0)).toBe(0);
  });

  it("aucun attribut style en ligne : la CSP les bloquerait (T06)", () => {
    const page = readFileSync("src/app/pilotage/page.tsx", "utf8");
    expect(page).not.toMatch(/style=\{/);
  });
});
