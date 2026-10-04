"use client";

import { useEffect, useRef, useState } from "react";

type Detector = { detect: (src: HTMLVideoElement) => Promise<{ rawValue: string }[]> };
type DetectorCtor = new (opts: { formats: string[] }) => Detector;

/** Le navigateur sait-il lire un QR (BarcodeDetector, Chrome sur Android) ? Sinon : saisie. */
export function canScan(): boolean {
  return typeof window !== "undefined" && "BarcodeDetector" in window && !!navigator.mediaDevices;
}

/**
 * Lecture du QR de la carte avec la caméra arrière, sans bibliothèque ni envoi d'image :
 * tout se passe dans le téléphone. La caméra s'arrête dès qu'un code est lu ou à la fermeture.
 */
export default function QrScanner({ onRead, onClose }: { onRead: (text: string) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setInterval> | null = null;
    let stopped = false;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        if (stopped || !video.current) return;
        video.current.srcObject = stream;
        await video.current.play();
        const Ctor = (window as unknown as { BarcodeDetector: DetectorCtor }).BarcodeDetector;
        const detector = new Ctor({ formats: ["qr_code"] });
        timer = setInterval(async () => {
          if (!video.current) return;
          const found = await detector.detect(video.current).catch(() => []);
          if (found.length) { onRead(found[0].rawValue); onClose(); }
        }, 300);
      } catch {
        setError("Caméra indisponible : saisissez le numéro.");
      }
    })();
    return () => {
      stopped = true;
      if (timer) clearInterval(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [onRead, onClose]);

  return (
    <div className="scanner">
      {error ? <p className="alert bad">{error}</p> : <video ref={video} muted playsInline aria-label="Caméra : visez le QR de la carte" />}
      <button type="button" className="ghost" onClick={onClose}>Fermer la caméra</button>
    </div>
  );
}
