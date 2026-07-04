"""Vivienda turística — registro oficial GVA + estimación INE.

1. GVA (dades obertes, dataset tur-gestur-vt): snapshot diario del Registro
   de Turismo con una fila por vivienda de uso turístico (municipio, plazas,
   fecha de alta). Reconstruimos la evolución de altas por año. LIMITACIÓN:
   el snapshot solo contiene las viviendas actualmente inscritas; las bajas
   desaparecen, así que "altas por año" es la antigüedad del parque vigente,
   no la serie histórica del stock.

2. INE (Medición del número de viviendas turísticas, tablas 39363 y 39366):
   estimación por scraping de plataformas, semestral (mayo/noviembre desde
   2024). OJO: la API Tempus de estas tablas está congelada en 2020; el
   export CSV de jaxiT3 sí está al día, por eso se usa el CSV.

-> data/vivienda_turistica.json
"""

import csv
import io
import re
from collections import defaultdict

from common import CACHE_DIR, die, download, fuente, log, write_json

GVA_DATASET = "https://dadesobertes.gva.es/es/dataset/tur-gestur-vt"
GVA_CSV = ("https://dadesobertes.gva.es/dataset/758f8f8e-c5af-4622-b268-a6c591710a51/"
           "resource/b1bdc28e-9813-422a-ab7a-63c21290493d/download/"
           "lista-de-viviendas-turisticas.csv")
INE_PAGE = "https://www.ine.es/experimental/viv_turistica/experimental_viv_turistica.htm"
INE_CSV_VT = "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/39363.csv"
INE_CSV_PCT = "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/39366.csv"


def num_es(s):
    """'341.001' -> 341001; '1,33' -> 1.33 (formato es del INE)."""
    s = s.strip()
    if not s or s in ("..", "."):
        return None
    s = s.replace(".", "").replace(",", ".")
    v = float(s)
    return int(v) if v.is_integer() else v


def parse_gva(path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    rd = csv.DictReader(io.StringIO(text), delimiter=";")
    need = {"cod_municipio", "cod_provincia", "municipio", "fecha_alta",
            "plazas_totales"}
    if not need.issubset(set(rd.fieldnames or [])):
        die(f"GVA: columnas cambiadas; hay {rd.fieldnames}")
    munis = {}
    for row in rd:
        if row["cod_provincia"].strip().zfill(2) != "12":
            continue
        cod = "12" + row["cod_municipio"].strip().zfill(3)
        m = munis.setdefault(cod, {"nombre": row["municipio"].strip().title(),
                                   "vt": 0, "plazas": 0,
                                   "altas_por_anyo": defaultdict(int)})
        m["vt"] += 1
        try:
            m["plazas"] += int(float(row["plazas_totales"] or 0))
        except ValueError:
            pass
        ma = re.search(r"(\d{4})", row["fecha_alta"] or "")
        if ma:
            m["altas_por_anyo"][ma.group(1)] += 1
    if not munis or "12040" not in munis:
        die("GVA: sin datos de la provincia 12 o falta Castelló ciudad")
    for m in munis.values():
        m["altas_por_anyo"] = dict(sorted(m["altas_por_anyo"].items()))
    return munis


def parse_ine_csv(path, campo_valor):
    """CSV jaxiT3: filas municipio×variable×periodo. Devuelve
    {cod5: {'nombre':…, series: {'2025-11': {campo: v}}}} de la provincia 12."""
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        rd = csv.DictReader(f, delimiter=";")
        for row in rd:
            mun = (row.get("Municipios") or "").strip()
            if not mun.startswith("12"):
                continue
            cod, _, nombre = mun.partition(" ")
            if len(cod) != 5:
                continue
            per = row["Periodo"].strip()          # p.ej. 2025M11
            pm = re.match(r"^(\d{4})M(\d{2})$", per)
            if not pm:
                die(f"INE VT: periodo inesperado {per!r}")
            key = f"{pm.group(1)}-{pm.group(2)}"
            variable = (row.get("Viviendas y plazas") or campo_valor).strip()
            val = num_es(row["Total"])
            if val is None:
                continue
            m = out.setdefault(cod, {"nombre": nombre.split("/")[0].strip(),
                                     "series": {}})
            serie = m["series"].setdefault(key, {})
            if "porcentaje" in variable.lower() or campo_valor == "pct_parque":
                serie["pct_parque"] = val
            elif variable == "Viviendas turísticas":
                serie["vt"] = val
            elif variable == "Plazas":
                serie["plazas"] = val
    if not out:
        die("INE VT: ninguna fila de la provincia 12")
    return out


def main():
    f_gva = download(GVA_CSV, CACHE_DIR / "gva_vt_registro.csv", force=True,
                     min_bytes=1_000_000)
    munis_gva = parse_gva(f_gva)
    total_vt = sum(m["vt"] for m in munis_gva.values())
    total_plazas = sum(m["plazas"] for m in munis_gva.values())
    if not (1000 <= total_vt <= 200_000):
        die(f"GVA: total provincial implausible {total_vt}")
    log(f"GVA: {total_vt} VT registradas en la provincia; "
        f"Castelló ciudad: {munis_gva['12040']['vt']}")

    f_vt = download(INE_CSV_VT, CACHE_DIR / "ine_vt_39363.csv", min_bytes=1_000_000)
    f_pct = download(INE_CSV_PCT, CACHE_DIR / "ine_vt_39366.csv", min_bytes=500_000)
    ine = parse_ine_csv(f_vt, "vt")
    for cod, m in parse_ine_csv(f_pct, "pct_parque").items():
        if cod in ine:
            for per, v in m["series"].items():
                ine[cod]["series"].setdefault(per, {}).update(v)
        else:
            ine[cod] = m
    if "12040" not in ine:
        die("INE VT: falta Castelló ciudad")
    ult = sorted(ine["12040"]["series"])[-1]
    vt_ine = ine["12040"]["series"][ult].get("vt")
    if not vt_ine or not (50 <= vt_ine <= 10_000):
        die(f"INE VT: valor implausible para Castelló en {ult}: {vt_ine}")
    log(f"INE: Castelló ciudad {ult}: {vt_ine} VT estimadas "
        f"({ine['12040']['series'][ult].get('pct_parque')}% del parque)")

    write_json("vivienda_turistica.json", {
        "gva": {
            "fuente": fuente(
                "Registre de Turisme de la Comunitat Valenciana (Turisme GVA, "
                "dades obertes)", GVA_DATASET, url_datos=GVA_CSV,
                nota="Snapshot diario de viviendas de uso turístico inscritas. "
                     "altas_por_anyo = año de alta de las viviendas HOY "
                     "inscritas (las bajas no aparecen).",
            ),
            "provincia": {"vt": total_vt, "plazas": total_plazas},
            "municipios": munis_gva,
        },
        "ine": {
            "fuente": fuente(
                "INE — Medición del número de viviendas turísticas en España",
                INE_PAGE, url_datos=INE_CSV_VT,
                nota="Estimación semestral (may/nov) por scraping de "
                     "plataformas con deduplicación. pct_parque = % sobre "
                     "viviendas censadas. Mide oferta en plataformas, no "
                     "registro oficial: la diferencia con el dato GVA aproxima "
                     "la oferta según dónde se mire.",
            ),
            "municipios": ine,
        },
    })


if __name__ == "__main__":
    main()
