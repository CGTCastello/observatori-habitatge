"""Construye los indicadores derivados y data/meta.json.

Uso:
    build_all.py            # calcula indicadores a partir de data/*.json
    build_all.py --fetch    # además ejecuta antes todos los fetchers

Cada indicador lleva su test de plausibilidad en RANGOS: si un valor se sale
del rango, el build aborta y no se publica nada. Los umbrales están pensados
para detectar cambios de formato o de unidad en las fuentes, no para
maquillar datos.
"""

import csv
import datetime
import json
import subprocess
import sys
from pathlib import Path

from common import DATA_DIR, ROOT, die, log, rnd, write_json

FETCHERS = ["fetch_serpavi.py", "fetch_ine.py", "fetch_cgpj.py", "fetch_vt.py",
            "fetch_aeat.py", "fetch_mivau.py", "fetch_fianzas.py"]

BASE = "2015"          # año base del índice 100 y del salario real
RETENCION_MEDIA = 0.21  # neto ≈ bruto × (1-0,21): ~6,5% SS + ~14,5% IRPF medio
SUPERFICIE_TIPO = 90    # m² de la "vivienda tipo" para años de salario

# test básico: (mínimo, máximo) plausible de cada cifra clave
RANGOS = {
    "indice100_alquiler_ultimo": (110, 260),
    "indice100_ipc_ultimo": (105, 175),
    "tasa_esfuerzo_ultima": (15, 60),        # % del salario neto medio
    "anyos_salario_ultimo": (3, 12),
    "salario_real_perdida_pct": (-25, 25),   # % vs 2015
    "desahucios_acumulado": (3000, 40000),
    "vt_castello_ine": (50, 5000),
    "fianzas_ultimo": (1000, 30000),
}


def check(clave, valor):
    lo, hi = RANGOS[clave]
    if valor is None or not (lo <= valor <= hi):
        die(f"test {clave}: {valor} fuera de rango [{lo}, {hi}]")
    log(f"  test {clave}: {valor} OK")


def carga(nombre):
    p = DATA_DIR / nombre
    if not p.exists():
        die(f"falta data/{nombre}; ejecuta los fetchers (--fetch)")
    return json.loads(p.read_text(encoding="utf-8"))


def carga_manual():
    smi = {}
    with open(ROOT / "scripts" / "manual_inputs.csv", encoding="utf-8") as f:
        filas = [l for l in f if not l.startswith("#")]
    for row in csv.DictReader(filas):
        if row["indicador"] == "smi_mensual":
            smi[row["fecha"]] = float(row["valor"])
    if len(smi) < 8:
        die("manual_inputs.csv: serie de SMI demasiado corta")
    return smi


def ultimo(d):
    return sorted(d)[-1]


def indice100(alq_muni, precio, salarios, ipc):
    series_fuente = {
        "alquiler_m2": {y: v["vc"]["eur_m2"]["mediana"]
                        for y, v in alq_muni.items() if "vc" in v},
        "compra_m2": precio["municipio"]["anual"],
        "salario": {y: v["salario_medio_eur"] for y, v in salarios["serie"].items()},
        # el año en curso del IPC es media parcial: fuera de la serie anual
        "ipc": {y: v for y, v in ipc["anual"].items()
                if y < str(datetime.date.today().year)},
    }
    out = {}
    for nombre, s in series_fuente.items():
        if BASE not in s:
            die(f"indice100: {nombre} no tiene año base {BASE}")
        base = s[BASE]
        out[nombre] = {y: rnd(100 * v / base, 1)
                       for y, v in sorted(s.items()) if y >= BASE}
    check("indice100_alquiler_ultimo", out["alquiler_m2"][ultimo(out["alquiler_m2"])])
    check("indice100_ipc_ultimo", out["ipc"][ultimo(out["ipc"])])
    return {"base": BASE, "series": out}


def tasa_esfuerzo(alq_muni, salarios):
    serie = {}
    for y, v in alq_muni.items():
        s = salarios["serie"].get(y)
        if "vc" not in v or not s:
            continue
        alquiler = v["vc"]["eur_mes"]["mediana"]
        neto_mes = s["salario_medio_eur"] * (1 - RETENCION_MEDIA) / 12
        serie[y] = {"alquiler_mes": alquiler, "salario_neto_mes": rnd(neto_mes, 0),
                    "tasa_pct": rnd(100 * alquiler / neto_mes, 1)}
    u = ultimo(serie)
    check("tasa_esfuerzo_ultima", serie[u]["tasa_pct"])
    return {"nota": f"neto estimado = bruto AEAT × {1 - RETENCION_MEDIA:.2f} "
                    "(cotizaciones + IRPF medio aproximado), en 12 pagas",
            "umbral_pct": 30, "serie": serie}


def anyos_para_comprar(precio, salarios):
    serie = {}
    for y, v in precio["municipio"]["anual"].items():
        s = salarios["serie"].get(y)
        if s:
            serie[y] = rnd(v * SUPERFICIE_TIPO / s["salario_medio_eur"], 1)
    u = ultimo(serie)
    check("anyos_salario_ultimo", serie[u])
    return {"nota": f"precio = valor tasado €/m² × {SUPERFICIE_TIPO} m²; "
                    "salario bruto anual AEAT", "serie": serie}


def salario_real(salarios, ipc):
    base_ipc = ipc["anual"][BASE]
    serie = {}
    for y, s in salarios["serie"].items():
        if y in ipc["anual"] and y >= BASE:
            real = s["salario_medio_eur"] * base_ipc / ipc["anual"][y]
            serie[y] = {"nominal": s["salario_medio_eur"], "real_base_2015": rnd(real, 0)}
    u = ultimo(serie)
    nominal_pct = 100 * (serie[u]["nominal"] / serie[BASE]["nominal"] - 1)
    real_pct = 100 * (serie[u]["real_base_2015"] / serie[BASE]["nominal"] - 1)
    check("salario_real_perdida_pct", rnd(real_pct, 1))
    return {"serie": serie,
            "resumen": {"anyo": u, "subida_nominal_pct": rnd(nominal_pct, 1),
                        "variacion_real_pct": rnd(real_pct, 1)}}


def desahucios_ind(desahucios):
    anual = desahucios["provincia"]["anual"]
    acum = desahucios["provincia"]["acumulado_desde_2013"]
    check("desahucios_acumulado", acum["total"])
    u = ultimo(anual)
    return {"anual_por_causa": anual, "acumulado": acum,
            "partido_judicial": desahucios["partido_judicial"]["anual"],
            "resumen": {"anyo": u, "total": anual[u]["total"],
                        "pct_lau": rnd(100 * anual[u]["lau"] / anual[u]["total"], 0)}}


def vt_ind(vt):
    cas_gva = vt["gva"]["municipios"]["12040"]
    cas_ine = vt["ine"]["municipios"]["12040"]["series"]
    u = ultimo(cas_ine)
    check("vt_castello_ine", cas_ine[u].get("vt"))
    # acumulado de altas del registro (parque vigente por año de alta)
    acum, total = {}, 0
    for y in sorted(cas_gva["altas_por_anyo"]):
        total += cas_gva["altas_por_anyo"][y]
        acum[y] = total
    top = sorted(vt["gva"]["municipios"].items(), key=lambda kv: -kv[1]["vt"])[:10]
    return {
        "castello": {"registro_gva": {"vt": cas_gva["vt"], "plazas": cas_gva["plazas"],
                                      "altas_acumuladas": acum},
                     "estimacion_ine": cas_ine},
        "top_municipios_gva": [{"codigo": c, "nombre": m["nombre"], "vt": m["vt"],
                                "plazas": m["plazas"]} for c, m in top],
        "provincia_gva": vt["gva"]["provincia"],
    }


def fianzas_ind(fianzas):
    completos = {y: d for y, d in fianzas["anual"].items() if not d["parcial"]}
    u = ultimo(completos)
    check("fianzas_ultimo", completos[u]["municipio"]["fianzas"])
    return {"anual": fianzas["anual"], "ultimo_completo": u}


def mapa_meta(mapa_alq, mapa_renta):
    secs_alq = set(mapa_alq["secciones"])
    ult_alq = max(y for s in mapa_alq["secciones"].values() for y in s)
    secs_renta = set(mapa_renta["secciones"])
    comunes = len(secs_alq & secs_renta)
    if comunes < 80:
        die(f"mapa: solo {comunes} secciones comunes alquiler/renta")
    return {"secciones_alquiler": len(secs_alq), "secciones_renta": len(secs_renta),
            "secciones_comunes": comunes, "anyo_alquiler": ult_alq}


def ultimo_dato(clave, datos):
    """Fecha del último dato de cada fuente, para data/meta.json."""
    try:
        if clave == "alquiler_serpavi":
            return datos["anyos"][-1]
        if clave == "ipc":
            return ultimo(datos["mensual"])
        if clave in ("compraventas", "hipotecas"):
            return ultimo(datos["mensual"] if clave == "compraventas"
                          else datos["mensual"]["numero"])
        if clave == "ipv":
            return ultimo(datos["base_2015"]["trimestral"])
        if clave == "renta_adrh":
            return ultimo(datos["municipio"]["series"])
        if clave == "desahucios":
            return ultimo(datos["provincia"]["trimestral"])
        if clave == "vivienda_turistica":
            return ultimo(datos["ine"]["municipios"]["12040"]["series"])
        if clave == "salarios_aeat":
            return ultimo(datos["serie"])
        if clave == "renta_irpf_municipios":
            return datos["anyo"]
        if clave == "precio_vivienda":
            return ultimo(datos["municipio"]["trimestral"])
        if clave == "fianzas":
            return ultimo(datos["anual"])
    except (KeyError, IndexError) as e:
        die(f"meta: no puedo determinar el último dato de {clave}: {e!r}")


def main():
    if "--fetch" in sys.argv:
        for f in FETCHERS:
            log(f"ejecutando {f}...")
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / f)])
            if r.returncode != 0:
                die(f"{f} ha fallado; build abortado")

    fuentes = {n: carga(f"{n}.json") for n in [
        "alquiler_serpavi", "ipc", "compraventas", "hipotecas", "ipv",
        "renta_adrh", "desahucios", "vivienda_turistica", "salarios_aeat",
        "renta_irpf_municipios", "precio_vivienda", "fianzas"]}
    mapa_alq = carga("mapa_alquiler.json")
    mapa_renta = carga("mapa_renta.json")
    smi = carga_manual()

    alq_muni = fuentes["alquiler_serpavi"]["municipio"]["series"]
    log("calculando indicadores...")
    indicadores = {
        "indice100": indice100(alq_muni, fuentes["precio_vivienda"],
                               fuentes["salarios_aeat"], fuentes["ipc"]),
        "tasa_esfuerzo": tasa_esfuerzo(alq_muni, fuentes["salarios_aeat"]),
        "anyos_para_comprar": anyos_para_comprar(fuentes["precio_vivienda"],
                                                 fuentes["salarios_aeat"]),
        "salario_real": salario_real(fuentes["salarios_aeat"], fuentes["ipc"]),
        "desahucios": desahucios_ind(fuentes["desahucios"]),
        "vivienda_turistica": vt_ind(fuentes["vivienda_turistica"]),
        "fianzas": fianzas_ind(fuentes["fianzas"]),
        "mapa": mapa_meta(mapa_alq, mapa_renta),
        "smi_mensual": smi,
    }
    write_json("indicadores.json", indicadores)

    meta = {
        "generado": datetime.datetime.now().isoformat(timespec="seconds"),
        "fuentes": {k: {"nombre": v["fuente"]["nombre"] if "fuente" in v
                        else v["gva"]["fuente"]["nombre"] + " / " + v["ine"]["fuente"]["nombre"],
                        "fecha_descarga": (v.get("fuente") or v["gva"]["fuente"])["fecha_descarga"],
                        "ultimo_dato": ultimo_dato(k, v)}
                    for k, v in fuentes.items()},
    }
    write_json("meta.json", meta)
    export_web()
    log("build completado")


# ficheros que consume la web (se copian a web/data/ y se inyectan en data.js
# como fallback para abrir index.html con file://)
FICHEROS_WEB = ["indicadores.json", "meta.json", "alquiler_serpavi.json",
                "salarios_aeat.json", "precio_vivienda.json", "hipotecas.json",
                "mapa_alquiler.json", "mapa_renta.json", "secciones.geojson"]


def export_web():
    destino = ROOT / "web" / "data"
    destino.mkdir(parents=True, exist_ok=True)
    inline = {}
    for nombre in FICHEROS_WEB:
        origen = DATA_DIR / nombre
        if not origen.exists():
            die(f"export web: falta data/{nombre}")
        contenido = origen.read_text(encoding="utf-8")
        (destino / nombre).write_text(contenido, encoding="utf-8")
        clave = nombre.replace(".geojson", "_geojson").replace(".json", "")
        inline[clave] = json.loads(contenido)
    datajs = destino / "data.js"
    datajs.write_text(
        "// Generado por build_all.py — NO editar a mano. Fallback para file://\n"
        "window.OBSERVATORI_DADES = "
        + json.dumps(inline, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    log(f"export web: {len(FICHEROS_WEB)} JSON + data.js "
        f"({datajs.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
