"""CGPJ — lanzamientos (desahucios ejecutados judicialmente).

Dos ficheros de "Efecto de la crisis en los órganos judiciales":
  1. Series por provincias (trimestral desde 2013, por causa: ejecución
     hipotecaria, LAU/alquiler, otros).
  2. Lanzamientos practicados por Partidos Judiciales 2013-2025 (anual),
     del que sacamos el partido judicial de Castelló de la Plana.

-> data/desahucios.json

Los ficheros se renombran en cada publicación trimestral: si una descarga
falla, buscar los enlaces "Series - ... por provincias" y "Lanzamientos
practicados por Partidos Judiciales" en PAGE_URL y actualizar las constantes.

Nota metodológica obligatoria en la web: el lanzamiento practicado mide
desahucios ejecutados con intervención judicial, no todos los abandonos
forzosos de vivienda.
"""

import re

from python_calamine import CalamineWorkbook

from common import CACHE_DIR, die, download, fuente, log, write_json

PAGE_URL = ("https://www.poderjudicial.es/cgpj/es/Temas/Estadistica-Judicial/"
            "Estudios-e-Informes/Efecto-de-la-Crisis-en-los-organos-judiciales/")
URL_PROV = ("https://www.poderjudicial.es/stfls/ESTADISTICA/FICHEROS/Crisis/"
            "Series%20-%20Efecto%20de%20la%20crisis%20en%20los%20organos%20"
            "judiciales%20por%20provincias%201T-2026_revisado.xlsx")
URL_PJ = ("https://www.poderjudicial.es/stfls/ESTADISTICA/FICHEROS/Crisis/"
          "Lanzamientos%20por%20PJs_2013_%202025.xlsx")

# hoja del fichero provincial -> clave de causa en el JSON
HOJAS_PROV = {
    "Lanzamientos pract. Total prov": "total",
    "Lanzamientos E.hipotecaria prov": "ejecucion_hipotecaria",
    "Lanzamientos L.A.U. prov": "lau",
    "Lanzamientos. Otros prov": "otros",
}
TRIM_RE = re.compile(r"^(\d{2})-T([1-4])$")
ANUAL_RE = re.compile(r"^Total\s*(\d{4})$")


def fila_castellon(rows):
    """Primera fila con CASTELLON en alguna de las 4 primeras columnas (la
    segunda aparición en las hojas provinciales es un bloque de tasas de
    variación, por eso nos quedamos con la primera)."""
    for r in rows:
        for c in r[:4]:
            if str(c).strip().upper().startswith("CASTELLON"):
                return r
    die("no encuentro la fila de Castellón; ¿cambió el formato?")


def parse_provincia(path):
    wb = CalamineWorkbook.from_path(str(path))
    faltan = set(HOJAS_PROV) - set(wb.sheet_names)
    if faltan:
        die(f"faltan hojas {faltan}; hojas: {wb.sheet_names}")
    trimestral, anual = {}, {}
    for hoja, causa in HOJAS_PROV.items():
        rows = wb.get_sheet_by_name(hoja).to_python(skip_empty_area=False)
        header = next((r for r in rows if any(TRIM_RE.match(str(c).strip())
                                              for c in r)), None)
        if header is None:
            die(f"hoja {hoja}: no encuentro la cabecera de trimestres")
        fila = fila_castellon(rows)
        for i, c in enumerate(header):
            c = str(c).replace("\r\n", " ").strip()
            v = fila[i] if i < len(fila) else None
            if v in (None, ""):
                continue
            m = TRIM_RE.match(c)
            if m:
                key = f"20{m.group(1)}-T{m.group(2)}"
                trimestral.setdefault(key, {})[causa] = int(float(v))
                continue
            m = ANUAL_RE.match(c)
            if m:
                anual.setdefault(m.group(1), {})[causa] = int(float(v))
    return trimestral, anual


def parse_partido_judicial(path):
    wb = CalamineWorkbook.from_path(str(path))
    rows = wb.get_sheet_by_name(wb.sheet_names[0]).to_python(skip_empty_area=False)
    anyos_row = next((r for r in rows
                      if sum(1 for c in r if re.match(r"^20\d{2}(\.0)?$", str(c).strip())) > 5), None)
    if anyos_row is None:
        die("PJ: no encuentro la fila de años")
    bloques = [(i, int(float(c))) for i, c in enumerate(anyos_row)
               if re.match(r"^20\d{2}(\.0)?$", str(c).strip())]
    fila = fila_castellon(rows)
    anual = {}
    for i, anyo in bloques:
        # cada bloque anual: TOTAL, ejec. hipotecaria, LAU, otros
        vals = [fila[j] if j < len(fila) else None for j in range(i, i + 4)]
        if any(v in (None, "") for v in vals):
            continue
        total, eh, lau, otros = (int(float(v)) for v in vals)
        if abs(total - (eh + lau + otros)) > max(3, total * 0.02):
            die(f"PJ {anyo}: total {total} != {eh}+{lau}+{otros}; ¿columnas movidas?")
        anual[str(anyo)] = {"total": total, "ejecucion_hipotecaria": eh,
                            "lau": lau, "otros": otros}
    if len(anual) < 8:
        die(f"PJ: solo {len(anual)} años")
    return anual


def main():
    f_prov = download(URL_PROV, CACHE_DIR / "cgpj_series_provincias.xlsx",
                      min_bytes=100_000)
    f_pj = download(URL_PJ, CACHE_DIR / "cgpj_lanzamientos_pj.xlsx",
                    min_bytes=20_000)

    trimestral, anual_prov = parse_provincia(f_prov)
    pj = parse_partido_judicial(f_pj)

    # completar años provinciales sin columna "Total AAAA" sumando trimestres
    por_anyo = {}
    for t, causas in trimestral.items():
        por_anyo.setdefault(t[:4], []).append(causas)
    for y, lst in por_anyo.items():
        if y not in anual_prov and len(lst) == 4:
            anual_prov[y] = {c: sum(q.get(c, 0) for q in lst)
                             for c in HOJAS_PROV.values()}

    for y, d in anual_prov.items():
        if "total" in d and not (50 <= d["total"] <= 5000):
            die(f"provincia {y}: total implausible {d['total']}")
    if not anual_prov or not trimestral:
        die("sin datos provinciales")

    acumulado = sum(d["total"] for d in anual_prov.values() if "total" in d)
    ult = sorted(anual_prov)[-1]
    log(f"provincia: {len(trimestral)} trimestres; {ult}: "
        f"{anual_prov[ult].get('total')} lanzamientos; acumulado 2013-{ult}: {acumulado}")
    ult_pj = sorted(pj)[-1]
    log(f"partido judicial Castelló {ult_pj}: {pj[ult_pj]['total']}")

    write_json("desahucios.json", {
        "fuente": fuente(
            "CGPJ — Efecto de la crisis en los órganos judiciales",
            PAGE_URL,
            nota="Lanzamientos practicados (desahucios ejecutados judicialmente). "
                 "Causas: ejecución hipotecaria, LAU (alquiler), otros. "
                 "No incluye abandonos forzosos sin intervención judicial.",
        ),
        "provincia": {"nombre": "Castellón", "trimestral": trimestral,
                      "anual": anual_prov,
                      "acumulado_desde_2013": {"hasta": ult, "total": acumulado}},
        "partido_judicial": {"nombre": "Castelló de la Plana", "anual": pj},
    })


if __name__ == "__main__":
    main()
