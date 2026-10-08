"use client";

/** « Enregistrer en PDF » : la boîte d'impression du téléphone ou de l'ordinateur (v1.1). */
export default function PrintButton({ label }: { label: string }) {
  return <button type="button" className="ghost no-print" onClick={() => window.print()}>{label}</button>;
}
