"""Censo de Población y Viviendas 2021 (INE) — parque de viviendas.

  - tpx 59525: viviendas por municipio y tipo (principal / no principal)
    -> % de viviendas no principales por municipio de la provincia.
  - tpx 59529: viviendas principales por régimen de tenencia en capitales y
    municipios >50.000 hab -> % en alquiler en Castelló de la Plana.

-> data/censo_viviendas.json

NOTA: el Censo 2021 publica tenencia y tipo de vivienda a nivel municipal;
el detalle por sección censal solo existió en el censo 2011 (desfasado), por
eso el mapa no lleva capa de tenencia.
"""

import csv
import io

import requests

from common import UA, die, fuente, log, rnd, write_json

URL_TIPO = "https://www.ine.es/jaxi/files/tpx/es/csv_bdsc/59525.csv"
URL_TENENCIA = "https://www.ine.es/jaxi/files/tpx/es/csv_bdsc/59529.csv"
PAGINA = "https://www.ine.es/jaxi/Tabla.htm?tpx=59525"


def filas(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    if r.status_code != 200:
        die(f"HTTP {r.status_code} en {url}")
    return list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")),
                           delimiter=";"))


def entero(s):
    s = s.strip().replace(".", "").replace(",", "")
    return int(s) if s.isdigit() else None


def main():
    # --- tipo de vivienda por municipio (toda la provincia) ---
    municipios = {}
    for fila in filas(URL_TIPO)[1:]:
        if len(fila) < 4 or not fila[1].strip().startswith("12"):
            continue
        cod, _, nombre = fila[1].strip().partition(" ")
        if len(cod) != 5:
            continue
        tipo, valor = fila[2].strip().lower(), entero(fila[3])
        if valor is None:
            continue
        m = municipios.setdefault(cod, {"nombre": nombre})
        if tipo == "total":
            m["viviendas"] = valor
        elif "no principal" in tipo:
            m["no_principales"] = valor
        elif "principal" in tipo:
            m["principales"] = valor
    for m in municipios.values():
        if "viviendas" in m and "no_principales" in m:
            m["pct_no_principales"] = rnd(100 * m["no_principales"] / m["viviendas"], 1)
    if len(municipios) < 100 or "12040" not in municipios:
        die(f"tipo de vivienda: {len(municipios)} municipios; ¿formato?")

    # --- tenencia en Castelló ciudad ---
    tenencia = {}
    for fila in filas(URL_TENENCIA)[1:]:
        if len(fila) < 3 or not fila[0].strip().startswith("12040"):
            continue
        regimen, valor = fila[1].strip().lower(), entero(fila[2])
        if valor is None:
            continue
        if regimen.startswith("total"):
            tenencia["principales"] = valor
        elif "propiedad" in regimen:
            tenencia["propiedad"] = valor
        elif "alquiler" in regimen:
            tenencia["alquiler"] = valor
        else:
            tenencia["otro"] = valor
    if "alquiler" not in tenencia or "principales" not in tenencia:
        die(f"tenencia: faltan categorías: {tenencia}")
    tenencia["pct_alquiler"] = rnd(100 * tenencia["alquiler"] / tenencia["principales"], 1)
    if not (10 <= tenencia["pct_alquiler"] <= 50):
        die(f"pct alquiler implausible: {tenencia['pct_alquiler']}")

    cas = municipios["12040"]
    log(f"Castelló ciudad: {cas['viviendas']} viviendas, "
        f"{cas['pct_no_principales']}% no principales; "
        f"{tenencia['pct_alquiler']}% de hogares en alquiler")
    write_json("censo_viviendas.json", {
        "fuente": fuente(
            "INE — Censo de Población y Viviendas 2021",
            PAGINA, url_datos=URL_TIPO,
            nota="Parque de viviendas por municipio (principales / no "
                 "principales) y régimen de tenencia de las principales en "
                 "Castelló de la Plana. Referencia: 1/1/2021.",
        ),
        "anyo": "2021",
        "municipios": municipios,
        "tenencia_castello": tenencia,
    })


if __name__ == "__main__":
    main()
