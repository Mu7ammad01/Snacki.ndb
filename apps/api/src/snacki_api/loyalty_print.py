"""Impression des cartes de fidélité (J8 bis), pour l'imprimeur. Deux mises en page :

- « cartes » (par défaut) : la carte complète, verso du menu, avec son QR et son numéro uniques
  déjà imprimés dans le cadre ; 2 cartes de 190 × 96,7 mm par page A4, traits de coupe compris ;
- « etiquettes » : planches A4 de 44 étiquettes 48,5 × 25,4 mm (type Avery 3657), à coller
  dans le cadre du verso si les menus sont déjà imprimés.

Le fond de la carte (print/carte-verso.jpg) est le rendu de la maquette « Carte de fidélité
Snacki » ; seuls le QR et le numéro changent d'une carte à l'autre.

Le fichier produit contient des numéros valides : il se garde hors du dépôt (`.gitignore`)
et se supprime une fois imprimé. Un numéro ne donne aucun droit sans le staff (ADR 0011).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from snacki_api.loyalty import display

MM = 72 / 25.4  # points PDF par millimètre
COLS, ROWS = 4, 11
LABEL_W, LABEL_H = 48.5, 25.4
MARGIN_X = (210 - COLS * LABEL_W) / 2
MARGIN_Y = (297 - ROWS * LABEL_H) / 2


def card_url(base_url: str, code: str) -> str:
    """Le numéro voyage dans le fragment (#) : il n'est jamais envoyé au serveur dans l'URL."""
    return f"{base_url.rstrip('/')}/carte#{display(code)}"


BACKGROUND = Path(__file__).resolve().parents[2] / "print" / "carte-verso.jpg"
CARD_W = 190.0  # mm ; la maquette fait 1080 × 550 px
CARD_H = CARD_W * 550 / 1080
PX = CARD_W / 1080  # mm par pixel de la maquette
QR_BOX = (380, 242.8, 250, 132)  # cadre blanc de la maquette : x, y, largeur, hauteur (px)


def _qr_png(url: str) -> BytesIO:
    import qrcode

    img = qrcode.make(url, box_size=8, border=1)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def write_cards(codes: list[str], base_url: str, out: Path, specimen: bool = False) -> int:
    """Cartes complètes, 2 par page A4 ; renvoie le nombre de pages."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    if not base_url.startswith("https://"):
        raise ValueError("Adresse du site en https:// attendue")
    pdf = canvas.Canvas(str(out), pagesize=(210 * MM, 297 * MM))
    pdf.setTitle("Snacki · cartes de fidélité")
    background = ImageReader(str(BACKGROUND))
    left = (210 - CARD_W) / 2
    tops = (28.0, 28.0 + CARD_H + 30.0)  # haut de chaque carte, en mm depuis le haut de la page
    for i, code in enumerate(codes):
        if i and i % 2 == 0:
            pdf.showPage()
        top = tops[i % 2]
        x0, y0 = left * MM, (297 - top - CARD_H) * MM
        pdf.drawImage(background, x0, y0, CARD_W * MM, CARD_H * MM)
        bx, by, bw, bh = QR_BOX
        qr = (bh - 16) * PX
        qx = x0 + (bx + 10) * PX * MM
        qy = y0 + (CARD_H - (by + bh) * PX + 8 * PX) * MM
        pdf.drawImage(ImageReader(_qr_png(card_url(base_url, code))), qx, qy, qr * MM, qr * MM)
        tx = qx + (qr + 2.5) * MM
        pdf.setFillColorRGB(0.37, 0.32, 0.21)
        pdf.setFont("Helvetica", 6.5)
        pdf.drawString(tx, qy + qr * MM - 4 * MM, "N° de carte")
        pdf.setFillColorRGB(0.12, 0.09, 0.03)
        pdf.setFont("Courier-Bold", 9.5)
        pdf.drawString(tx, qy + qr * MM - 9 * MM, display(code)[:8])
        pdf.drawString(tx, qy + qr * MM - 13 * MM, display(code)[9:])
        if specimen:
            pdf.saveState()
            pdf.setFillColorRGB(0.78, 0.18, 0.23)
            pdf.setFillAlpha(0.35)
            pdf.setFont("Helvetica-Bold", 30)
            pdf.translate(x0 + CARD_W * MM * 0.62, y0 + CARD_H * MM * 0.55)
            pdf.rotate(18)
            pdf.drawCentredString(0, 0, "SPÉCIMEN")
            pdf.restoreState()
        _crop_marks(pdf, x0, y0, CARD_W * MM, CARD_H * MM)
    pdf.save()
    return (len(codes) + 1) // 2


def _crop_marks(pdf, x: float, y: float, w: float, h: float) -> None:
    """Traits de coupe aux quatre coins, hors de la carte."""
    gap, length = 2 * MM, 5 * MM
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(0.3)
    for cx, sx in ((x, -1), (x + w, 1)):
        for cy, sy in ((y, -1), (y + h, 1)):
            pdf.line(cx + sx * gap, cy, cx + sx * (gap + length), cy)
            pdf.line(cx, cy + sy * gap, cx, cy + sy * (gap + length))


def write_labels(codes: list[str], base_url: str, out: Path) -> int:
    """Écrit les étiquettes ; renvoie le nombre de pages."""
    import qrcode  # bibliothèques du script seulement, hors de l'image de l'API
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    if not base_url.startswith("https://"):
        raise ValueError("Adresse du site en https:// attendue")
    pdf = canvas.Canvas(str(out), pagesize=(210 * MM, 297 * MM))
    pdf.setTitle("Snacki · étiquettes de fidélité")
    per_page = COLS * ROWS
    for i, code in enumerate(codes):
        if i and i % per_page == 0:
            pdf.showPage()
        slot = i % per_page
        col, row = slot % COLS, slot // COLS
        x = (MARGIN_X + col * LABEL_W) * MM
        y = (297 - MARGIN_Y - (row + 1) * LABEL_H) * MM
        img = qrcode.make(card_url(base_url, code), box_size=4, border=1)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        size = 21 * MM
        pdf.drawImage(ImageReader(buf), x + 2 * MM, y + 2.2 * MM, size, size)
        tx = x + 24.5 * MM
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(tx, y + 17 * MM, "Snacki")
        pdf.setFont("Helvetica", 6.5)
        pdf.drawString(tx, y + 13.2 * MM, "Carte fidélité")
        pdf.setFont("Courier-Bold", 7.5)
        pdf.drawString(tx, y + 6 * MM, display(code))
    pdf.save()
    return (len(codes) + per_page - 1) // per_page
