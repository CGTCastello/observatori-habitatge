"""Genera las OG images (1200x630) para compartir en redes.

Lee la cifra estrella de data/indicadores.json y compone una tarjeta sobria
rojinegra -> web/img/og-va.png (y og-es.png cuando exista la versión ES).
Ejecutar tras build_all.py si han cambiado los datos.
"""

import json

from PIL import Image, ImageDraw, ImageFont

from common import DATA_DIR, ROOT, die, log

ANCHO, ALTO = 1200, 630
NEGRE, ROIG, BLANC, GRIS = "#1b1a18", "#d81f1f", "#ffffff", "#b5b5b5"
FONT = "/System/Library/Fonts/Helvetica.ttc"


def fuente(px, bold=True):
    try:
        return ImageFont.truetype(FONT, px, index=1 if bold else 0)
    except OSError:
        die(f"no encuentro la fuente {FONT}")


def tarjeta(destino, titular, cifra, sub, pie):
    img = Image.new("RGB", (ANCHO, ALTO), NEGRE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 18, ALTO], fill=ROIG)                 # franja lateral
    d.text((70, 60), titular, font=fuente(44), fill=BLANC)
    d.text((70, 170), cifra, font=fuente(170), fill=ROIG)
    d.text((70, 390), sub, font=fuente(46), fill=BLANC)
    d.rectangle([70, 500, 620, 506], fill=ROIG)
    d.text((70, 530), pie, font=fuente(28, bold=False), fill=GRIS)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, optimize=True)
    log(f"escrito {destino.relative_to(ROOT)} "
        f"({destino.stat().st_size / 1024:.0f} KB)")


def main():
    ind = json.loads((DATA_DIR / "indicadores.json").read_text(encoding="utf-8"))
    s = ind["indice100"]["series"]["alquiler_m2"]
    ult = sorted(s)[-1]
    subida = round(s[ult] - 100)
    tarjeta(
        ROOT / "web" / "img" / "og-va.png",
        "Observatori de l'Habitatge de Castelló",
        f"+{subida}%",
        f"ha pujat el lloguer real des de 2015 ({ult})",
        "Dades oficials: SERPAVI · INE · AEAT · CGPJ  —  CGT Castelló",
    )


if __name__ == "__main__":
    main()
