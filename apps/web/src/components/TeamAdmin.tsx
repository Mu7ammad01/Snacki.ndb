"use client";

import { useState, type FormEvent } from "react";

import { ROLE_LABEL, type Role, type StaffMe, type StaffMember } from "@/lib/staff";

const ROLES: Role[] = ["caissier", "gerante", "admin"];

/** Écran « Équipe » (admin) : ajouter une adresse Google, changer un rôle, désactiver un compte. */
export default function TeamAdmin({ me, initial }: { me: StaffMe; initial: StaffMember[] }) {
  const [team, setTeam] = useState(initial);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("caissier");
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  async function call(url: string, method: "POST" | "PATCH", body: object) {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = (await r.json().catch(() => ({}))) as StaffMember & { detail?: unknown };
      if (r.status === 401) { window.location.assign("/connexion"); return null; }
      if (!r.ok) {
        setMsg({ text: typeof data.detail === "string" ? data.detail : "Action refusée", bad: true });
        return null;
      }
      return data;
    } catch {
      setMsg({ text: "Service momentanément indisponible", bad: true });
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    const added = await call("/api/staff", "POST", { email, role });
    if (added) {
      setTeam((t) => [...t, added]);
      setEmail("");
      setMsg({ text: `${added.email} peut maintenant se connecter.`, bad: false });
    }
  }

  async function update(member: StaffMember, change: { role?: Role; active?: boolean }) {
    const updated = await call(`/api/staff/${member.id}`, "PATCH", change);
    if (updated) setTeam((t) => t.map((m) => (m.id === updated.id ? updated : m)));
  }

  return (
    <section className="track">
      <h2>Équipe</h2>
      <p className="muted">Seules ces adresses Google peuvent se connecter. Un changement s&apos;applique immédiatement.</p>
      {msg && <p className={msg.bad ? "alert bad" : "alert"} role="status">{msg.text}</p>}

      <ul className="team">
        {team.map((m) => (
          <li key={m.id} className={m.active ? "" : "off"}>
            <div>
              <b>{m.display_name ?? m.email}</b>
              <span className="muted">{m.email}{m.active ? "" : " · désactivé"}</span>
            </div>
            {m.id === me.id ? (
              <span className="muted">{ROLE_LABEL[m.role]} (vous)</span>
            ) : (
              <div className="team-actions">
                <select
                  aria-label={`Rôle de ${m.email}`}
                  value={m.role}
                  disabled={busy}
                  onChange={(e) => update(m, { role: e.target.value as Role })}
                >
                  {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                </select>
                <button type="button" className="ghost" disabled={busy} onClick={() => update(m, { active: !m.active })}>
                  {m.active ? "Désactiver" : "Réactiver"}
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>

      <form onSubmit={add} className="team-add">
        <div className="field">
          <label htmlFor="new-email">Adresse Google</label>
          <input id="new-email" type="email" required maxLength={254} value={email}
            onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
        </div>
        <div className="field">
          <label htmlFor="new-role">Rôle</label>
          <select id="new-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </select>
        </div>
        <button className="primary" type="submit" disabled={busy || !email}>Ajouter à l&apos;équipe</button>
      </form>
    </section>
  );
}
