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
    "esfuerzo_1smi_pct": (25, 70),           # alquiler mediano sobre neto de 1 SMI
    "subida_absorbida_pct": (10, 90),        # % de la subida salarial comida por el alquiler
    "esfuerzo_pensionista_pct": (15, 70),
    "anyos_ahorro_entrada_smi": (2, 40),
}

# Parámetros IRPF/SS 2024 para el neto por niveles salariales (indicador
# "esfuerzo por niveles"). Modelo simplificado pero citable: cotización del
# trabajador, gastos deducibles, reducción por rendimientos del trabajo
# (art. 20 LIRPF, cuantías 2024), mínimo personal general y escala estatal
# duplicada como aproximación de la tarifa total.
IRPF_2024 = {
    "ss_pct": 0.0648,
    "gastos": 2000,
    "reduccion": [(14_852, None, 7302),
                  (17_673.52, 1.75, 7302), (19_747.5, 1.14, 2364.34)],
    "minimo_personal": 5550,
    "escala": [(12_450, 0.19), (20_200, 0.24), (35_200, 0.30),
               (60_000, 0.37), (300_000, 0.45), (float("inf"), 0.47)],
}


def neto_anual_2024(bruto, cotiza_ss=True):
    """Neto anual estimado con los parámetros IRPF_2024. Aproximación
    documentada en la metodología; no sustituye a una nómina real.
    cotiza_ss=False para pensiones (no cotizan a la Seguridad Social)."""
    p = IRPF_2024
    ss = bruto * p["ss_pct"] if cotiza_ss else 0.0
    rn = bruto - ss - p["gastos"]
    reduccion = 0.0
    if rn <= p["reduccion"][0][0]:
        reduccion = p["reduccion"][0][2]
    else:
        for tope, pendiente, base_red in p["reduccion"][1:]:
            if rn <= tope:
                limite_previo = (p["reduccion"][0][0] if base_red == 7302
                                 else p["reduccion"][1][0])
                reduccion = max(0.0, base_red - pendiente * (rn - limite_previo))
                break
    base = max(0.0, rn - reduccion)

    def tarifa(cantidad):
        cuota, previo = 0.0, 0.0
        for tope, tipo in p["escala"]:
            tramo = min(cantidad, tope) - previo
            if tramo <= 0:
                break
            cuota += tramo * tipo
            previo = tope
        return cuota

    cuota = max(0.0, tarifa(base) - tarifa(min(base, p["minimo_personal"])))
    return bruto - ss - cuota


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


def esfuerzo_niveles(alq_muni, salarios, smi):
    """Tasa de esfuerzo del alquiler mediano según el nivel salarial (año de
    los tramos AEAT): 1/1,5/2 SMI y salario medio, con % de asalariados de la
    provincia que cobra hasta ese nivel."""
    t = salarios["tramos_smi"]
    anyo = t["anyo"]
    if anyo not in alq_muni or anyo not in smi:
        die(f"esfuerzo_niveles: falta alquiler o SMI de {anyo}")
    alquiler = alq_muni[anyo]["vc"]["eur_mes"]
    smi_anual = smi[anyo] * 14

    # % de asalariados hasta n SMI, acumulando tramos
    total, acum, hasta = t["asalariados_total"], 0, {}
    for etiqueta, n in t["tramos"].items():
        acum += n
        tope = etiqueta.split(" a ")[-1].replace(",", ".")
        if tope in ("1", "1.5", "2"):
            hasta[float(tope)] = rnd(100 * acum / total, 1)

    niveles = {}
    for nombre, bruto, mult in [("1 SMI", smi_anual, 1.0),
                                ("1,5 SMI", smi_anual * 1.5, 1.5),
                                ("2 SMI", smi_anual * 2, 2.0),
                                ("salario medio", None, None)]:
        if bruto is None:
            bruto = salarios["serie"][anyo]["salario_medio_eur"]
        neto_mes = neto_anual_2024(bruto) / 12
        niveles[nombre] = {
            "bruto_anual": rnd(bruto, 0),
            "neto_mes_estimado": rnd(neto_mes, 0),
            "tasa_alquiler_mediano_pct": rnd(100 * alquiler["mediana"] / neto_mes, 1),
            "tasa_alquiler_p25_pct": rnd(100 * alquiler["p25"] / neto_mes, 1),
            "pct_asalariados_hasta": hasta.get(mult),
        }
    check("esfuerzo_1smi_pct", niveles["1 SMI"]["tasa_alquiler_mediano_pct"])
    return {
        "anyo": anyo,
        "nota": "Neto estimado con cotización del 6,48%, gastos deducibles, "
                "reducción por rendimientos del trabajo y escala estatal "
                "duplicada (parámetros 2024): aproximación, no una nómina. "
                "pct_asalariados_hasta incluye jornadas parciales y años "
                "incompletos (fuente AEAT, sin ajuste por tiempo trabajado).",
        "alquiler": alquiler,
        "niveles": niveles,
    }


def subida_absorbida(alq_muni, salarios):
    """¿Qué parte de la subida salarial desde 2015 se ha comido el alquiler?"""
    ult = max(y for y in alq_muni if "vc" in alq_muni[y]
              and y in salarios["serie"])
    d_alq = (alq_muni[ult]["vc"]["eur_mes"]["mediana"]
             - alq_muni[BASE]["vc"]["eur_mes"]["mediana"])
    d_bruto_mes = (salarios["serie"][ult]["salario_medio_eur"]
                   - salarios["serie"][BASE]["salario_medio_eur"]) / 12
    d_neto_mes = d_bruto_mes * (1 - RETENCION_MEDIA)
    pct_neto = rnd(100 * d_alq / d_neto_mes, 0)
    check("subida_absorbida_pct", pct_neto)
    return {
        "periodo": f"{BASE}-{ult}",
        "subida_alquiler_mes": rnd(d_alq, 0),
        "subida_salario_bruto_mes": rnd(d_bruto_mes, 0),
        "subida_salario_neto_mes": rnd(d_neto_mes, 0),
        "pct_absorbido_bruto": rnd(100 * d_alq / d_bruto_mes, 0),
        "pct_absorbido_neto": pct_neto,
        "nota": "Comparación de la subida del alquiler mediano mensual con la "
                "subida del salario medio mensual (12 pagas) en el mismo "
                "periodo. Neto con el mismo factor que la tasa de esfuerzo.",
    }


def comparativa_provincias(alquiler):
    comp = alquiler.get("comparativa_provincias")
    if not comp or len(comp) != 3:
        die("comparativa_provincias ausente en alquiler_serpavi.json")
    out = {}
    for cod, d in comp.items():
        s = d["eur_m2_mediana_vc"]
        if BASE not in s:
            die(f"comparativa: {d['nombre']} sin año base")
        out[cod] = {"nombre": d["nombre"],
                    "indice": {y: rnd(100 * v / s[BASE], 1)
                               for y, v in sorted(s.items()) if y >= BASE},
                    "eur_m2": {y: v for y, v in sorted(s.items()) if y >= BASE}}
    return {"base": BASE, "provincias": out}


def esfuerzo_colectivos(alq_muni, desglose, pensiones):
    """Tasa de esfuerzo del alquiler mediano por colectivos (edad, sexo,
    sector y pensionistas), con el neto del modelo IRPF 2024."""
    anyo = desglose["anyo"]
    if anyo not in alq_muni:
        die(f"esfuerzo_colectivos: sin alquiler de {anyo}")
    mediana = alq_muni[anyo]["vc"]["eur_mes"]["mediana"]

    def item(bruto, n, cotiza_ss=True):
        neto_mes = neto_anual_2024(bruto, cotiza_ss) / 12
        return {"bruto_anual": rnd(bruto, 0), "neto_mes_estimado": rnd(neto_mes, 0),
                "tasa_alquiler_mediano_pct": rnd(100 * mediana / neto_mes, 1),
                "personas": n}

    out = {"anyo": anyo, "alquiler_mediano_mes": mediana,
           "edad": {}, "sexo": {}, "sectores": {}, "pensionistas": {}}
    for k, v in desglose["edad"].items():
        out["edad"][k] = item(v["salario_medio_eur"], v["asalariados"])
    for k, v in desglose["sexo"].items():
        out["sexo"][k] = item(v["salario_medio_eur"], v["asalariados"])
    for k, v in sorted(desglose["sectores"].items(),
                       key=lambda kv: -kv[1]["asalariados"])[:6]:
        out["sectores"][k] = item(v["salario_medio_eur"], v["asalariados"])
    for k in ("total", "varon", "mujer"):
        p = pensiones[k]
        out["pensionistas"][k] = item(p["pension_media_anual_eur"],
                                      p["pensionistas"], cotiza_ss=False)
    check("esfuerzo_pensionista_pct",
          out["pensionistas"]["total"]["tasa_alquiler_mediano_pct"])
    out["nota"] = ("Salarios medios AEAT sin ajuste por jornada ni tiempo "
                   "trabajado: en colectivos con mucha parcialidad (jóvenes, "
                   "hostelería) la tasa refleja lo INGRESADO en el año, no el "
                   "salario por hora. Pensiones sin cotización a la SS.")
    return out


def ahorro_entrada(precio, salarios, smi):
    """Años para ahorrar la entrada (20% + 10% de gastos) de una vivienda de
    90 m² guardando el 15% del neto."""
    ult_p = ultimo(precio["municipio"]["anual"])
    coste = precio["municipio"]["anual"][ult_p] * SUPERFICIE_TIPO * 0.30
    ult_s = ultimo(salarios["serie"])
    niveles = {}
    for nombre, bruto in [("1 SMI", smi[ult_s] * 14),
                          ("salario medio", salarios["serie"][ult_s]["salario_medio_eur"])]:
        ahorro_anual = neto_anual_2024(bruto) * 0.15
        niveles[nombre] = rnd(coste / ahorro_anual, 1)
    check("anyos_ahorro_entrada_smi", niveles["1 SMI"])
    return {
        "anyo_precio": ult_p, "anyo_salario": ult_s,
        "entrada_eur": rnd(coste, 0),
        "nota": f"Vivienda de {SUPERFICIE_TIPO} m² a valor tasado de la "
                "ciudad; entrada = 20% no financiado + 10% de gastos e "
                "impuestos; ahorro del 15% del neto estimado.",
        "anyos": niveles,
    }


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


def exporta_municipios(alq_municipios, fuentes):
    """data/municipios.json: resumen por municipio de la provincia para las
    fichas de formación (alquiler, fianzas, renta IRPF, VT, parque)."""
    irpf = fuentes["renta_irpf_municipios"]["municipios"]
    fian = fuentes["fianzas"]["anual"]
    vt_gva = fuentes["vivienda_turistica"]["gva"]["municipios"]
    vt_ine = fuentes["vivienda_turistica"]["ine"]["municipios"]
    censo = fuentes["censo_viviendas"]["municipios"]
    out = {}
    for cod, d in alq_municipios["municipios"].items():
        anyos = sorted(d["series"])
        alq = {}
        for y in (BASE, anyos[-1]):
            vc = d["series"].get(y, {}).get("vc", {})
            if "eur_mes" in vc or "eur_m2" in vc:
                alq[y] = {"eur_mes": vc.get("eur_mes", {}).get("mediana"),
                          "eur_m2": vc.get("eur_m2", {}).get("mediana"),
                          "n": vc.get("n")}
        m = {"nombre": d["nombre"], "alquiler": alq, "ultimo_anyo": anyos[-1]}
        if cod in fian.get(sorted(fian)[-1], {}).get("municipios", {}):
            m["fianzas"] = {y: fian[y]["municipios"][cod]
                            for y in sorted(fian)
                            if cod in fian[y].get("municipios", {})
                            and not fian[y]["parcial"]}
        if cod in irpf:
            m["renta_irpf"] = irpf[cod]
        if cod in vt_gva:
            m["vt_gva"] = {"vt": vt_gva[cod]["vt"], "plazas": vt_gva[cod]["plazas"]}
        if cod in vt_ine and vt_ine[cod]["series"]:
            u = sorted(vt_ine[cod]["series"])[-1]
            m["vt_ine"] = {"periodo": u, **vt_ine[cod]["series"][u]}
        if cod in censo:
            m["censo_2021"] = censo[cod]
        out[cod] = m
    if len(out) < 10 or "12040" not in out:
        die(f"municipios.json: solo {len(out)} municipios")
    write_json("municipios.json", {
        "nota": "Resumen municipal para las fichas de formación. Fuentes y "
                "años: los de cada bloque (ver data/meta.json).",
        "municipios": out,
    })


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
            return ultimo(datos["trimestral"])
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
        if clave in ("salarios_desglose", "pensiones", "censo_viviendas"):
            return datos["anyo"]
        if clave == "irav":
            return datos["ultimo"]["periodo"]
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
        "renta_irpf_municipios", "precio_vivienda", "fianzas",
        "salarios_desglose", "pensiones", "censo_viviendas", "irav"]}
    alq_municipios = carga("alquiler_municipios.json")
    mapa_alq = carga("mapa_alquiler.json")
    mapa_renta = carga("mapa_renta.json")
    smi = carga_manual()

    alq_muni = fuentes["alquiler_serpavi"]["municipio"]["series"]
    log("calculando indicadores...")
    indicadores = {
        "indice100": indice100(alq_muni, fuentes["precio_vivienda"],
                               fuentes["salarios_aeat"], fuentes["ipc"]),
        "tasa_esfuerzo": tasa_esfuerzo(alq_muni, fuentes["salarios_aeat"]),
        "esfuerzo_niveles": esfuerzo_niveles(alq_muni, fuentes["salarios_aeat"], smi),
        "anyos_para_comprar": anyos_para_comprar(fuentes["precio_vivienda"],
                                                 fuentes["salarios_aeat"]),
        "salario_real": salario_real(fuentes["salarios_aeat"], fuentes["ipc"]),
        "desahucios": desahucios_ind(fuentes["desahucios"]),
        "vivienda_turistica": vt_ind(fuentes["vivienda_turistica"]),
        "fianzas": fianzas_ind(fuentes["fianzas"]),
        "mapa": mapa_meta(mapa_alq, mapa_renta),
        "smi_mensual": smi,
        "subida_absorbida": subida_absorbida(alq_muni, fuentes["salarios_aeat"]),
        "comparativa_provincias": comparativa_provincias(fuentes["alquiler_serpavi"]),
        "esfuerzo_colectivos": esfuerzo_colectivos(
            alq_muni, fuentes["salarios_desglose"], fuentes["pensiones"]),
        "ahorro_entrada": ahorro_entrada(fuentes["precio_vivienda"],
                                         fuentes["salarios_aeat"], smi),
        "censo": {"anyo": "2021",
                  "castello": {**fuentes["censo_viviendas"]["municipios"]["12040"],
                               "tenencia": fuentes["censo_viviendas"]["tenencia_castello"]}},
        "irav": fuentes["irav"]["ultimo"],
    }
    write_json("indicadores.json", indicadores)
    exporta_municipios(alq_municipios, fuentes)

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
                "mapa_alquiler.json", "mapa_renta.json", "secciones.geojson",
                "irav.json", "censo_viviendas.json"]


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
