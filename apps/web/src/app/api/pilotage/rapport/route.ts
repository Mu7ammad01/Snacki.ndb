import { NextResponse, type NextRequest } from "next/server";

import { validDay } from "@/lib/pilotage";
import { staffFetch } from "@/lib/server/staff";

/** Rapport Excel (v1.1) : relais de l'API, dates validées, jamais mis en cache. */
export async function GET(request: NextRequest) {
  const start = validDay(request.nextUrl.searchParams.get("start"));
  const end = validDay(request.nextUrl.searchParams.get("end"));
  if (!start || !end) return NextResponse.json({ detail: "Période invalide" }, { status: 422 });
  try {
    const r = await staffFetch(`/v1/pilotage/rapport.xlsx?start=${start}&end=${end}`);
    if (!r.ok) {
      const out = NextResponse.json(await r.json().catch(() => ({})), { status: r.status });
      out.headers.set("Cache-Control", "no-store");
      return out;
    }
    return new NextResponse(await r.arrayBuffer(), {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": `attachment; filename="snacki-rapport-${start}-${end}.xlsx"`,
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Service momentanément indisponible" }, { status: 503 });
  }
}
