"""Genera las fichas municipales de formación (formacion/fichas/*.md).

Una ficha por municipio de la provincia con datos suficientes (los que tienen
renta IRPF publicada, es decir >1.000 declarantes). Cada cifra lleva año y
fuente. Ejecutar tras build_all.py.
"""

import json
import re
import unicodedata

from common import DATA_DIR, ROOT, die, log

DESTINO = ROOT / "formacion" / "fichas"


def slug(nombre):
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def eur(v):
    return f"{v:,.0f}".replace(",", ".") if v is not None else "s.d."


def ficha(cod, m):
    n = m["nombre"]
    lineas = [f"# {n} — dades d'habitatge i renda", ""]

    alq = m.get("alquiler", {})
    anyos_alq = sorted(alq)
    if anyos_alq:
        u = anyos_alq[-1]
        l = alq[u]
        lineas += [f"## Lloguer real (SERPAVI, contractes declarats, {u})", ""]
        if l.get("eur_mes"):
            lineas.append(f"- Lloguer mitjà (mediana): **{eur(l['eur_mes'])} €/mes**"
                          + (f" · {l['eur_m2']} €/m²" if l.get("eur_m2") else ""))
        if l.get("n"):
            lineas.append(f"- Contractes testimoni: {eur(l['n'])}")
        if "2015" in alq and alq["2015"].get("eur_m2") and l.get("eur_m2"):
            pujada = 100 * (l["eur_m2"] / alq["2015"]["eur_m2"] - 1)
            lineas.append(f"- Pujada del €/m² des de 2015: **+{pujada:.0f}%**")
        lineas.append("")

    fian = m.get("fianzas", {})
    if fian:
        u = sorted(fian)[-1]
        f = fian[u]
        lineas += [f"## Contractes nous de lloguer (fiances GVA, {u})", "",
                   f"- Fiances dipositades: **{eur(f['fianzas'])}** contractes",
                   f"- Import mitjà de la fiança (≈ renda mensual dels "
                   f"contractes NOUS): **{eur(f.get('importe_medio_eur'))} €**", ""]

    r = m.get("renta_irpf")
    if r:
        lineas += ["## Renda declarada (AEAT IRPF, 2023)", "",
                   f"- Renda bruta mitjana per declaració: **{eur(r['renta_bruta_media'])} €** "
                   f"(mediana {eur(r['renta_bruta_mediana'])} €)",
                   f"- Renda disponible mitjana: {eur(r['renta_disponible_media'])} €",
                   f"- Posició estatal per renda bruta: {eur(r['pos_nacional'])} "
                   f"de ~2.900 municipis >1.000 hab", ""]

    c = m.get("censo_2021")
    if c and c.get("pct_no_principales") is not None:
        lineas += ["## Parc de vivendes (Cens 2021, INE)", "",
                   f"- Vivendes totals: {eur(c['viviendas'])}",
                   f"- **{c['pct_no_principales']}% no principals** "
                   f"(buides, segones residències...)", ""]

    vt = m.get("vt_gva")
    if vt:
        linea_vt = (f"- Registrades a la GVA: **{eur(vt['vt'])}** "
                    f"({eur(vt['plazas'])} places)")
        ine = m.get("vt_ine")
        if ine and ine.get("vt") is not None:
            linea_vt += (f" · estimades per l'INE en plataformes: "
                         f"{eur(ine['vt'])} ({ine['periodo']})")
        lineas += ["## Vivendes turístiques", "", linea_vt, ""]

    lineas += ["---",
               "*Observatori de l'Habitatge de Castelló (CGT Castelló). Fonts "
               "oficials: SERPAVI/MIVAU, GVA dades obertes, AEAT, INE. Cada "
               "bloc indica la font i l'any de la dada.*", ""]
    return "\n".join(lineas)


def main():
    datos = json.loads((DATA_DIR / "municipios.json").read_text(encoding="utf-8"))
    munis = {c: m for c, m in datos["municipios"].items() if "renta_irpf" in m}
    if len(munis) < 20:
        die(f"solo {len(munis)} municipios con ficha; ¿falta renta IRPF?")
    DESTINO.mkdir(parents=True, exist_ok=True)
    for f in DESTINO.glob("*.md"):
        f.unlink()
    indice = ["# Fichas municipales — índice", ""]
    for cod, m in sorted(munis.items(), key=lambda kv: kv[1]["nombre"]):
        nombre_f = f"{slug(m['nombre'])}.md"
        (DESTINO / nombre_f).write_text(ficha(cod, m), encoding="utf-8")
        alq = m.get("alquiler", {}).get(m.get("ultimo_anyo", ""), {})
        indice.append(f"- [{m['nombre']}]({nombre_f}) — lloguer "
                      f"{eur(alq.get('eur_mes'))} €/mes ({m.get('ultimo_anyo')})")
    (DESTINO / "INDICE.md").write_text("\n".join(indice) + "\n", encoding="utf-8")
    log(f"{len(munis)} fichas en formacion/fichas/")


if __name__ == "__main__":
    main()
