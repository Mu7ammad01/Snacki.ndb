"""Impression des cartes de fidélité (J8 bis), pour l'imprimeur. Deux mises en page :

- « cartes » (par défaut) : la carte complète, verso du menu, avec son QR et son numéro uniques
  déjà imprimés dans le cadre ; 2 cartes de 190 × 96,7 mm par page A4, traits de coupe compris ;
- « cartes4 » : la même carte en 135 × 68,8 mm, 4 par page A4 paysage (deux fois moins de papier) ;
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
QR_BOX = (380, 242.8, 250, 132)  # cadre blanc de la maquette 1080 × 550 px : x, y, l, h (px)
# Mises en page des cartes : (largeur de page, hauteur de page, largeur de carte) en mm,
# puis le coin haut-gauche de chaque carte (mm depuis le haut-gauche de la page).
LAYOUTS = {
    2: (210.0, 297.0, 190.0, ((10.0, 28.0), (10.0, 28.0 + 96.7 + 30.0))),  # A4 portrait
    4: (297.0, 210.0, 135.0, ((8.5, 31.0), (153.5, 31.0), (8.5, 109.8), (153.5, 109.8))),
}


def _qr_png(url: str) -> BytesIO:
    import qrcode

    img = qrcode.make(url, box_size=8, border=1)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def write_cards(
    codes: list[str], base_url: str, out: Path, specimen: bool = False, per_page: int = 2
) -> int:
    """Cartes complètes, 2 (19 × 9,7 cm) ou 4 (13,5 × 6,9 cm) par page A4 ; renvoie les pages."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    if not base_url.startswith("https://"):
        raise ValueError("Adresse du site en https:// attendue")
    if per_page not in LAYOUTS:
        raise ValueError("2 ou 4 cartes par page")
    page_w, page_h, card_w, slots = LAYOUTS[per_page]
    card_h = card_w * 550 / 1080
    px = card_w / 1080  # mm par pixel de la maquette
    k = card_w / 190  # échelle des textes par rapport à la grande carte
    pdf = canvas.Canvas(str(out), pagesize=(page_w * MM, page_h * MM))
    pdf.setTitle("Snacki · cartes de fidélité")
    background = ImageReader(str(BACKGROUND))
    for i, code in enumerate(codes):
        if i and i % per_page == 0:
            pdf.showPage()
        left, top = slots[i % per_page]
        x0, y0 = left * MM, (page_h - top - card_h) * MM
        pdf.drawImage(background, x0, y0, card_w * MM, card_h * MM)
        bx, by, bw, bh = QR_BOX
        qr = (bh - 16) * px
        qx = x0 + (bx + 10) * px * MM
        qy = y0 + (card_h - (by + bh) * px + 8 * px) * MM
        pdf.drawImage(ImageReader(_qr_png(card_url(base_url, code))), qx, qy, qr * MM, qr * MM)
        tx = qx + (qr + 2.5 * k) * MM
        pdf.setFillColorRGB(0.37, 0.32, 0.21)
        pdf.setFont("Helvetica", 6.5 * k)
        pdf.drawString(tx, qy + (qr - 4 * k) * MM, "N° de carte")
        pdf.setFillColorRGB(0.12, 0.09, 0.03)
        pdf.setFont("Courier-Bold", 9.5 * k)
        pdf.drawString(tx, qy + (qr - 9 * k) * MM, display(code)[:8])
        pdf.drawString(tx, qy + (qr - 13 * k) * MM, display(code)[9:])
        if specimen:
            pdf.saveState()
            pdf.setFillColorRGB(0.78, 0.18, 0.23)
            pdf.setFillAlpha(0.35)
            pdf.setFont("Helvetica-Bold", 30 * k)
            pdf.translate(x0 + card_w * MM * 0.62, y0 + card_h * MM * 0.55)
            pdf.rotate(18)
            pdf.drawCentredString(0, 0, "SPÉCIMEN")
            pdf.restoreState()
        _crop_marks(pdf, x0, y0, card_w * MM, card_h * MM)
    pdf.save()
    return (len(codes) + per_page - 1) // per_page


def _crop_marks(pdf, x: float, y: float, w: float, h: float) -> None:
    """Traits de coupe aux quatre coins, hors de la carte."""
    gap, length = 1.5 * MM, 3.5 * MM
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
