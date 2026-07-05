"""GVA — Registro de fianzas de alquiler de viviendas.

Un dataset CKAN por ejercicio (slug viv-reg-fia-AAAA, disponibles desde 2020)
con una fila por fianza depositada: municipio, importe y si fue devuelta.
El número de fianzas depositadas ≈ contratos de alquiler firmados ese año.

-> data/fianzas.json  (provincia 12 y Castelló de la Plana)

El año en curso está incompleto: se marca con "parcial": true y la web no
debe usarlo en series interanuales sin avisar.
"""

import csv
import datetime
import io

from common import die, fuente, get_json, log, rnd, write_json
import requests

from common import UA

API = "https://dadesobertes.gva.es/api/3/action/package_show?id=viv-reg-fia-{}"
PORTAL = "https://dadesobertes.gva.es/es/dataset/viv-reg-fia-{}"
ANYO_INICIO = 2020


def csv_url(anyo):
    data = get_json(API.format(anyo))
    if not data.get("success"):
        return None
    for res in data["result"]["resources"]:
        if res["format"] == "CSV":
            return res["url"]
    die(f"dataset {anyo} sin recurso CSV")


def parse_anyo(anyo, url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=300)
    if r.status_code != 200:
        die(f"HTTP {r.status_code} en {url}")
    rd = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";")
    need = {"cod_provincia", "cod_municipio", "municipio", "importe_fianza",
            "devuelta"}
    if not need.issubset(set(rd.fieldnames or [])):
        die(f"fianzas {anyo}: columnas cambiadas: {rd.fieldnames}")
    prov = {"n": 0, "devueltas": 0}
    por_muni = {}
    for row in rd:
        if row["cod_provincia"].strip().zfill(2) != "12":
            continue
        dev = row["devuelta"].strip().upper() in ("SI", "SÍ", "S")
        prov["n"] += 1
        prov["devueltas"] += dev
        cod = "12" + row["cod_municipio"].strip().zfill(3)
        m = por_muni.setdefault(cod, {"nombre": row["municipio"].strip().title(),
                                      "n": 0, "importes": []})
        m["n"] += 1
        try:
            m["importes"].append(float(row["importe_fianza"].replace(",", ".")))
        except (ValueError, AttributeError):
            pass
    if "12040" not in por_muni:
        die(f"fianzas {anyo}: falta Castelló ciudad")
    municipios = {cod: {"nombre": m["nombre"], "fianzas": m["n"],
                        "importe_medio_eur": (rnd(sum(m["importes"]) / len(m["importes"]), 0)
                                              if m["importes"] else None)}
                  for cod, m in por_muni.items()}
    cas = municipios["12040"]
    return {
        "provincia": {"fianzas": prov["n"], "devueltas": prov["devueltas"]},
        "municipio": {"fianzas": cas["fianzas"],
                      "importe_medio_eur": cas["importe_medio_eur"]},
        "municipios": municipios,
    }


def main():
    hoy = datetime.date.today()
    anual = {}
    for anyo in range(ANYO_INICIO, hoy.year + 1):
        url = csv_url(anyo)
        if url is None:
            log(f"aviso: dataset {anyo} no existe")
            continue
        datos = parse_anyo(anyo, url)
        datos["parcial"] = anyo == hoy.year
        anual[str(anyo)] = datos
        log(f"{anyo}: {datos['municipio']['fianzas']} fianzas en Castelló ciudad "
            f"({datos['provincia']['fianzas']} en la provincia)"
            + (" [año en curso, parcial]" if datos["parcial"] else ""))
    completos = [a for a, d in anual.items() if not d["parcial"]]
    if len(completos) < 4:
        die(f"solo {len(completos)} años completos de fianzas")
    ult = sorted(completos)[-1]
    n = anual[ult]["municipio"]["fianzas"]
    if not (1000 <= n <= 30_000):
        die(f"fianzas {ult} en Castelló implausible: {n}")
    write_json("fianzas.json", {
        "fuente": fuente(
            "Registre de fiances d'arrendaments urbans (GVA, dades obertes)",
            PORTAL.format(ult),
            nota="Una fianza depositada ≈ un contrato de alquiler firmado ese "
                 "año. La fianza legal es 1 mensualidad: el importe medio "
                 "aproxima la renta mensual de los contratos NUEVOS del año. "
                 "El año en curso (parcial: true) está incompleto.",
        ),
        "anual": anual,
    })


if __name__ == "__main__":
    main()
