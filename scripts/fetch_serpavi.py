"""SERPAVI (MIVAU) — alquiler real de contratos declarados fiscalmente.

Descarga la BD íntegra del Sistema Estatal de Índices de Alquiler de Vivienda
(XLSX, 2011-2024) y extrae:
  - Serie anual de la provincia de Castellón (CPRO 12) y de Castelló de la
    Plana (CUMUN 12040)  -> data/alquiler_serpavi.json
  - Alquiler €/m² por sección censal de Castelló ciudad -> data/mapa_alquiler.json

Estadísticos de la BD: mediana (M), percentil 25 y percentil 75. VC = vivienda
colectiva (pisos), VU = unifamiliar. Si el Ministerio cambia el diseño de
registro, el script aborta sin tocar los JSON existentes.

La URL del XLSX cambia con cada publicación anual: si la descarga falla,
buscar el enlace "BD Sistema Estatal Índices de Alquiler de Vivienda" en
PAGE_URL y actualizar XLSX_URL.
"""

import re
import sys

from python_calamine import CalamineWorkbook

from common import (
    CACHE_DIR,
    CPRO_CASTELLO,
    CUMUN_CASTELLO,
    die,
    download,
    fuente,
    log,
    rnd,
    write_json,
)

PAGE_URL = "https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi"
XLSX_URL = (
    "https://cdn.mivau.gob.es/portal-web-mivau/vivienda/serpavi/"
    "2026-03-09_bd_SERPAVI_2011-2024%20-%20DEFINITIVO%20WEB.xlsx"
)
CACHE_FILE = CACHE_DIR / "bd_serpavi_2011-2024.xlsx"

# Columnas de la BD: <VARIABLE>_<ESTADISTICO>_<TIPOLOGIA>_<AA>
COL_RE = re.compile(
    r"^(BI_ALVHEPCO|ALQM2(?:mes)?_LV|ALQTBID12|SLVM2)_(M|25|75|TVC|TVU)(?:_(VC|VU))?_(\d{2})$"
)
VAR_KEY = {"BI_ALVHEPCO": "n", "ALQM2_LV": "eur_m2", "ALQM2mes_LV": "eur_m2",
           "ALQTBID12": "eur_mes", "SLVM2": "superficie_m2"}
STAT_KEY = {"M": "mediana", "25": "p25", "75": "p75"}


def parse_columns(header):
    """Devuelve {índice_columna: (año, tipología, variable, estadístico)}."""
    cols = {}
    for i, name in enumerate(header):
        m = COL_RE.match(str(name).strip())
        if not m:
            continue
        var, stat, tip, yy = m.groups()
        if var == "BI_ALVHEPCO":  # BI_ALVHEPCO_TVC_11: la tipología va en 'stat'
            tip = {"TVC": "VC", "TVU": "VU"}[stat]
            stat = None
        cols[i] = (2000 + int(yy), tip.lower(), VAR_KEY[var],
                   STAT_KEY.get(stat) if stat else None)
    return cols


def row_to_series(row, cols):
    """Convierte una fila ancha en {año: {vc: {...}, vu: {...}}}."""
    series = {}
    for i, (year, tip, var, stat) in cols.items():
        if i >= len(row):
            continue
        val = rnd(row[i], 0 if var == "n" else 2)
        if val is None:
            continue
        y = series.setdefault(str(year), {})
        t = y.setdefault(tip, {})
        if var == "n":
            t["n"] = int(val)
        else:
            t.setdefault(var, {})[stat] = val
    return series


def extract(sheet_rows, code_col, code_match, name_col=None):
    """Busca filas cuyo código coincide y devuelve (nombre, series) por fila."""
    header = sheet_rows[0]
    cols = parse_columns(header)
    if not cols:
        die(f"diseño de registro no reconocido; cabecera: {header[:8]}")
    out = []
    for row in sheet_rows[1:]:
        code = str(row[code_col]).strip()
        if code_match(code):
            name = str(row[name_col]).strip() if name_col is not None else None
            out.append((code, name, row_to_series(row, cols)))
    return out


def main():
    force = "--force" in sys.argv
    download(XLSX_URL, CACHE_FILE, force=force, min_bytes=10_000_000)
    log("abriendo XLSX (puede tardar un poco)...")
    wb = CalamineWorkbook.from_path(str(CACHE_FILE))
    need = {"Provincias", "Municipios", "Secciones censales"}
    if not need.issubset(set(wb.sheet_names)):
        die(f"faltan hojas {need - set(wb.sheet_names)} en el XLSX; hojas: {wb.sheet_names}")

    # --- Provincia 12 + comparativa (València 46, Alacant 03) ---
    rows = wb.get_sheet_by_name("Provincias").to_python(skip_empty_area=False)
    prov = extract(rows, 0, lambda c: c == CPRO_CASTELLO, name_col=1)
    if len(prov) != 1:
        die(f"esperaba 1 fila de provincia 12, hay {len(prov)}")
    comparativa = {}
    for cod, _, series in extract(rows, 0, lambda c: c in ("03", "12", "46"),
                                  name_col=1):
        nombre = next(n for c, n, _ in
                      extract(rows, 0, lambda x: x == cod, name_col=1))
        comparativa[cod] = {
            "nombre": nombre,
            "eur_m2_mediana_vc": {y: v["vc"]["eur_m2"]["mediana"]
                                  for y, v in series.items() if "vc" in v},
        }
    if len(comparativa) != 3:
        die(f"comparativa: esperaba 3 provincias, hay {len(comparativa)}")

    # --- Municipios de la provincia (todos los que tienen datos) ---
    rows = wb.get_sheet_by_name("Municipios").to_python(skip_empty_area=False)
    muni = extract(rows, 2, lambda c: c == CUMUN_CASTELLO, name_col=3)
    if len(muni) != 1:
        die(f"esperaba 1 fila del municipio {CUMUN_CASTELLO}, hay {len(muni)}")
    municipios = {}
    for cod, nombre, series in extract(rows, 2,
                                       lambda c: c.startswith(CPRO_CASTELLO),
                                       name_col=3):
        con_datos = {y: v for y, v in series.items() if "vc" in v}
        if con_datos:
            municipios[cod] = {"nombre": nombre, "series": con_datos}
    if len(municipios) < 10 or CUMUN_CASTELLO not in municipios:
        die(f"municipios provinciales con datos: {len(municipios)}; ¿formato?")

    # --- Secciones censales de la ciudad ---
    rows = wb.get_sheet_by_name("Secciones censales").to_python(skip_empty_area=False)
    secs = extract(rows, 4, lambda c: c.startswith(CUMUN_CASTELLO))
    if len(secs) < 50:
        die(f"solo {len(secs)} secciones censales de {CUMUN_CASTELLO}; formato cambiado?")

    # --- Validación de plausibilidad (no publicar datos absurdos) ---
    m_series = muni[0][2]
    years_with_data = sorted(y for y, v in m_series.items() if "vc" in v)
    if not years_with_data:
        die("el municipio no tiene ningún año con datos de vivienda colectiva")
    last = years_with_data[-1]
    med = m_series[last]["vc"]["eur_m2"]["mediana"]
    if not (2 <= med <= 20):
        die(f"mediana €/m² {last} fuera de rango plausible: {med}")
    log(f"Castelló de la Plana {last}: {med} €/m²/mes mediana (VC), "
        f"{m_series[last]['vc']['n']} viviendas testigo")

    src = fuente(
        "SERPAVI — Sistema Estatal de Índices de Alquiler de Vivienda (MIVAU)",
        PAGE_URL,
        url_datos=XLSX_URL,
        nota="Contratos reales declarados fiscalmente. Estadísticos: mediana, "
             "P25, P75. vc=vivienda colectiva (pisos), vu=unifamiliar. "
             "eur_m2: €/m²/mes; eur_mes: € mensuales del inmueble completo.",
    )

    write_json("alquiler_serpavi.json", {
        "fuente": src,
        "anyos": years_with_data,
        "provincia": {"codigo": prov[0][0], "nombre": prov[0][1], "series": prov[0][2]},
        "municipio": {"codigo": muni[0][0], "nombre": muni[0][1], "series": muni[0][2]},
        "comparativa_provincias": comparativa,
    })
    write_json("alquiler_municipios.json", {
        "fuente": src,
        "nota": "Municipios de la provincia de Castellón con datos SERPAVI "
                "(vivienda colectiva).",
        "municipios": municipios,
    })

    # Mapa: solo VC €/m² y n por sección y año (compacto para la web)
    secciones = {}
    for cusec, _, series in secs:
        per_year = {}
        for y, v in series.items():
            vc = v.get("vc", {})
            if "eur_m2" in vc:
                per_year[y] = {"eur_m2": vc["eur_m2"]["mediana"],
                               "eur_mes": vc.get("eur_mes", {}).get("mediana"),
                               "n": vc.get("n")}
        if per_year:
            secciones[cusec] = per_year
    if len(secciones) < 30:
        die(f"solo {len(secciones)} secciones con datos; formato cambiado?")
    write_json("mapa_alquiler.json", {
        "fuente": src,
        "municipio": CUMUN_CASTELLO,
        "nota_codigos": "CUSEC de 10 dígitos (seccionado Censo 2011)",
        "secciones": secciones,
    })
    log(f"OK: {len(secciones)} secciones censales con datos de alquiler")


if __name__ == "__main__":
    main()
