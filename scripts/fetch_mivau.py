"""MIVAU — valor tasado de la vivienda libre (€/m², trimestral).

Boletín Online del Ministerio (apps.fomento.gob.es/BoletinOnline2, sección 35):
  - 35101000.XLS: serie provincial desde 1995 (una hoja por bloque de 4 años)
  - 35103500.XLS: municipios >25.000 hab desde 2005 (una hoja por trimestre)

-> data/precio_vivienda.json  (provincia de Castellón y Castelló de la Plana)

El diseño de columnas del fichero municipal cambió con los años (antes "Valor
medio", ahora desglose por antigüedad + "Total"): el parser se guía por las
cabeceras, no por posiciones fijas.
"""

import re

from python_calamine import CalamineWorkbook

from common import CACHE_DIR, die, download, fuente, log, rnd, write_json

PAGE_URL = ("https://www.mivau.gob.es/el-ministerio/observatorios-y-estadisticas/"
            "estadisticas/valor-tasado-vivienda")
URL_PROV = "https://apps.fomento.gob.es/BoletinOnline2/sedal/35101000.XLS"
URL_MUNI = "https://apps.fomento.gob.es/BoletinOnline2/sedal/35103500.XLS"


# Rango de plausibilidad del €/m² tasado: la serie provincial va de ~435
# (1995) a ~1.465 (2026). Las hojas traen columnas de trimestres aún no
# publicados con variaciones o notas al pie (1,3 / 14,6 ...) que se colaban
# como si fueran precios y estropeaban la media anual.
EUR_M2_MIN, EUR_M2_MAX = 200.0, 6000.0


def val(c):
    if isinstance(c, (int, float)):
        v = rnd(c, 1)
        return v if EUR_M2_MIN <= v <= EUR_M2_MAX else None
    return None  # 'n.r' (no representativo), vacíos, texto


def parse_provincial(path):
    """{ '1995-T1': eur_m2, ... } para la provincia de Castellón."""
    wb = CalamineWorkbook.from_path(str(path))
    serie = {}
    for hoja in wb.sheet_names:
        rows = wb.get_sheet_by_name(hoja).to_python(skip_empty_area=False)
        anyo_row = next((r for r in rows
                         if sum(1 for c in r if re.match(r"^Año \d{4}", str(c))) >= 2),
                        None)
        cast = next((r for r in rows
                     if str(r[1]).strip().lower().startswith("castellón")), None)
        if anyo_row is None or cast is None:
            die(f"hoja {hoja!r}: no encuentro años o fila de Castellón")
        for i, c in enumerate(anyo_row):
            m = re.match(r"^Año (\d{4})", str(c))
            if not m:
                continue
            for q in range(4):
                v = val(cast[i + q]) if i + q < len(cast) else None
                if v is not None:
                    serie[f"{m.group(1)}-T{q + 1}"] = v
    return serie


def parse_municipal(path):
    """{ '2005-T1': eur_m2_total, ... } para Castelló de la Plana."""
    wb = CalamineWorkbook.from_path(str(path))
    serie = {}
    for hoja in wb.sheet_names:
        m = re.match(r"^T([1-4])A(\d{4})\s*$", hoja)
        if not m:
            die(f"hoja municipal inesperada: {hoja!r}")
        key = f"{m.group(2)}-T{m.group(1)}"
        rows = wb.get_sheet_by_name(hoja).to_python(skip_empty_area=False)
        hdr_i = next((i for i, r in enumerate(rows)
                      if str(r[2]).strip() == "Municipio"), None)
        if hdr_i is None:
            die(f"hoja {hoja}: sin cabecera 'Municipio'")
        # etiqueta de cada columna = concatenación de las 3 filas de cabecera
        ncols = len(rows[hdr_i])
        labels = [" ".join(str(rows[hdr_i + k][c]) for k in range(3)
                           if hdr_i + k < len(rows) and c < len(rows[hdr_i + k])).lower()
                  for c in range(ncols)]
        col = next((c for c, l in enumerate(labels) if "total" in l), None)
        if col is None:
            col = next((c for c, l in enumerate(labels) if "valor medio" in l), None)
        if col is None:
            die(f"hoja {hoja}: no identifico la columna de valor ({labels})")
        cast = next((r for r in rows
                     if str(r[2]).strip().lower().startswith("castellón de la plana")),
                    None)
        if cast is None:
            die(f"hoja {hoja}: sin fila de Castelló de la Plana")
        v = val(cast[col])
        if v is not None:
            serie[key] = v
    return serie


def anual(serie):
    """Media anual de los años con 4 trimestres."""
    por_anyo = {}
    for k, v in serie.items():
        por_anyo.setdefault(k[:4], []).append(v)
    return {y: rnd(sum(v) / 4, 1) for y, v in sorted(por_anyo.items()) if len(v) == 4}


def main():
    f_prov = download(URL_PROV, CACHE_DIR / "mivau_tasado_prov.xls", min_bytes=50_000)
    f_muni = download(URL_MUNI, CACHE_DIR / "mivau_tasado_muni.xls", min_bytes=500_000)
    prov = parse_provincial(f_prov)
    muni = parse_municipal(f_muni)
    if len(prov) < 100:
        die(f"provincia: solo {len(prov)} trimestres")
    if len(muni) < 60:
        die(f"municipio: solo {len(muni)} trimestres")
    prov_a, muni_a = anual(prov), anual(muni)
    ult = sorted(muni_a)[-1]
    if not (500 <= muni_a[ult] <= 5000):
        die(f"valor municipal {ult} implausible: {muni_a[ult]}")
    log(f"provincia: {len(prov)} trimestres (desde {sorted(prov)[0]}); "
        f"municipio: {len(muni)} (desde {sorted(muni)[0]})")
    log(f"Castelló ciudad {ult}: {muni_a[ult]} €/m² tasado (media anual)")
    write_json("precio_vivienda.json", {
        "fuente": fuente(
            "MIVAU — Valor tasado de la vivienda libre",
            PAGE_URL, url_datos=URL_PROV,
            nota="€/m² medio de tasación de vivienda libre. Serie provincial "
                 "desde 1995 y de Castelló de la Plana (municipios >25.000 hab) "
                 "desde 2005. anual = media de los 4 trimestres.",
        ),
        "provincia": {"nombre": "Castellón", "trimestral": prov, "anual": prov_a},
        "municipio": {"nombre": "Castelló de la Plana", "trimestral": muni,
                      "anual": muni_a},
    })


if __name__ == "__main__":
    main()
