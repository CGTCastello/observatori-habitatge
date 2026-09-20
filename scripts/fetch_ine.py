"""INE (API Tempus, https://servicios.ine.es/wstempus/js/) — descarga:

  - IPC índice general, provincia de Castellón (tabla 24081)   -> data/ipc.json
  - ETDP compraventas de viviendas, provincia (tabla 6149)     -> data/compraventas.json
  - Hipotecas sobre viviendas, provincia (tabla 76317)         -> data/hipotecas.json
  - IPV por CCAA, Comunitat Valenciana (tablas 76201 y 79540)  -> data/ipv.json
  - ADRH renta por sección censal, Castelló ciudad (t. 30962)  -> data/renta_adrh.json
                                                                  data/mapa_renta.json

Los IDs de tabla se verificaron contra la API en julio de 2026; si el INE
reorganiza una tabla el filtrado por nombre dejará de casar y el script
abortará sin tocar los JSON existentes.
"""

import re
import unicodedata

from common import die, fuente, get_json, log, rnd, write_json

BASE = "https://servicios.ine.es/wstempus/js/ES"

T_IPC = 24081        # Índice general por provincias, serie mensual larga
T_ETDP = 6149        # Viviendas transmitidas según título de adquisición (prov.)
T_HIPO = 76317       # Hipotecas por naturaleza de finca, nº e importe (prov.)
# El INE retiró en 2026 la tabla 76201 (IPV base 2015). La serie trimestral
# por CCAA vive ahora en la 80270; si vuelve a cambiar, se busca con
# TABLAS_OPERACION/IPV y se coge la de "Índices por CCAA ... Trimestrales".
T_IPV = 80270        # IPV trimestral por CCAA
T_ADRH = 30962       # ADRH provincia de Castellón (municipios/distritos/secciones)
T_IRAV = 72975       # Índice de Referencia de Arrendamientos de Vivienda (nacional)


def norm(s):
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def datos_tabla(tid, nult=500):
    data = get_json(f"{BASE}/DATOS_TABLA/{tid}?nult={nult}")
    if not isinstance(data, list) or not data:
        die(f"tabla {tid}: respuesta vacía o inesperada de la API")
    return data


def datos(s):
    """Puntos de datos de una serie (la API usa la clave 'Data')."""
    d = s.get("Data") or s.get("Datos")
    if not d:
        die(f"serie {s.get('COD')} sin datos")
    return d


def pick(series, *terms, forbid=()):
    """Series cuyo nombre (normalizado) contiene todos los términos."""
    out = []
    for s in series:
        n = norm(s["Nombre"])
        if all(t in n for t in terms) and not any(f in n for f in forbid):
            out.append(s)
    return out


def pick_one(series, *terms, forbid=()):
    got = pick(series, *terms, forbid=forbid)
    if len(got) != 1:
        die(f"esperaba 1 serie con {terms}, hay {len(got)}: "
            f"{[s['Nombre'] for s in got[:5]]}")
    return got[0]


def fecha_ym(punto):
    """(año, mes) de un punto de datos. Fecha viene en ms epoch a medianoche
    local de Madrid; sumamos 12 h antes de leerla en UTC para no caer en el
    mes anterior."""
    import datetime as dt
    d = dt.datetime.utcfromtimestamp(punto["Fecha"] / 1000 + 43200)
    return d.year, d.month


def mensual(serie_datos):
    return {f"{y}-{m:02d}": rnd(p["Valor"], 3)
            for p in serie_datos for y, m in [fecha_ym(p)]}


def trimestral(serie_datos):
    return {f"{y}-T{(m - 1) // 3 + 1}": rnd(p["Valor"], 3)
            for p in serie_datos for y, m in [fecha_ym(p)]}


def fuente_ine(tabla, desc):
    return fuente(f"INE — {desc}",
                  f"https://www.ine.es/jaxiT3/Tabla.htm?t={tabla}",
                  url_datos=f"{BASE}/DATOS_TABLA/{tabla}")


def fetch_ipc():
    series = datos_tabla(T_IPC, nult=500)
    s = pick_one(series, "castell", "indice general")
    mens = mensual(datos(s))
    if len(mens) < 200:
        die(f"IPC: solo {len(mens)} meses, esperaba una serie larga")
    ultimo = sorted(mens)[-1]
    if not (60 <= mens[ultimo] <= 160):
        die(f"IPC: último valor implausible {mens[ultimo]}")
    anual = {}
    for ym, v in mens.items():
        anual.setdefault(ym[:4], []).append(v)
    # El INE rebasa el IPC cada pocos años: detectamos el año base (media=100)
    medias = {y: sum(v) / len(v) for y, v in anual.items() if len(v) == 12}
    base = min(medias, key=lambda y: abs(medias[y] - 100))
    if abs(medias[base] - 100) > 0.5:
        die(f"IPC: no encuentro el año base (candidato {base}={medias[base]:.2f})")
    write_json("ipc.json", {
        "fuente": fuente_ine(T_IPC, "IPC. Índice general, provincia de Castellón"),
        "serie": s["COD"],
        "base": base,
        "nota": f"Índice base {base}=100 (serie enlazada). anual = media de "
                "los meses disponibles del año.",
        "mensual": mens,
        "anual": {y: rnd(sum(v) / len(v), 3) for y, v in sorted(anual.items())},
    })
    log(f"IPC: {len(mens)} meses, último {ultimo} = {mens[ultimo]}")


def fetch_compraventas():
    series = datos_tabla(T_ETDP, nult=300)
    s = pick_one(series, "castell", "compraventa")
    mens = mensual(datos(s))
    anual = {}
    for ym, v in mens.items():
        anual.setdefault(ym[:4], []).append(v)
    anual_sum = {y: int(sum(v)) for y, v in sorted(anual.items()) if len(v) == 12}
    if not anual_sum:
        die("compraventas: ningún año completo")
    ult = sorted(anual_sum)[-1]
    if not (1000 <= anual_sum[ult] <= 40000):
        die(f"compraventas {ult} implausible: {anual_sum[ult]}")
    write_json("compraventas.json", {
        "fuente": fuente_ine(T_ETDP, "ETDP. Compraventas de viviendas inscritas, "
                                     "provincia de Castellón"),
        "serie": s["COD"],
        "nota": "Número de compraventas de viviendas inscritas en los registros. "
                "anual solo incluye años con 12 meses publicados.",
        "mensual": mens,
        "anual": anual_sum,
    })
    log(f"compraventas: {ult} = {anual_sum[ult]}/año")


def fetch_hipotecas():
    series = datos_tabla(T_HIPO, nult=300)
    s_num = pick_one(series, "castell", "viviendas", "numero de hipotecas")
    s_imp = pick_one(series, "castell", "viviendas", "importe de hipotecas")
    num, imp = mensual(datos(s_num)), mensual(datos(s_imp))
    anual = {}
    for ym in num:
        if ym in imp and num[ym] and imp[ym] is not None:
            a = anual.setdefault(ym[:4], {"n": 0, "imp": 0.0, "meses": 0})
            a["n"] += num[ym]
            a["imp"] += imp[ym]
            a["meses"] += 1
    anual_out = {}
    for y, a in sorted(anual.items()):
        if a["meses"] == 12:
            # el importe de la tabla viene en miles de €
            anual_out[y] = {"numero": int(a["n"]),
                            "importe_medio_eur": rnd(a["imp"] * 1000 / a["n"], 0)}
    if not anual_out:
        die("hipotecas: ningún año completo")
    ult = sorted(anual_out)[-1]
    medio = anual_out[ult]["importe_medio_eur"]
    if not (30_000 <= medio <= 500_000):
        die(f"hipotecas: importe medio implausible {medio} € (¿cambió la unidad?)")
    write_json("hipotecas.json", {
        "fuente": fuente_ine(T_HIPO, "Estadística de Hipotecas. Viviendas, "
                                     "provincia de Castellón"),
        "series": {"numero": s_num["COD"], "importe": s_imp["COD"]},
        "nota": "Hipotecas constituidas sobre viviendas. importe mensual en "
                "miles de €; importe_medio_eur en €.",
        "mensual": {"numero": num, "importe_miles_eur": imp},
        "anual": anual_out,
    })
    log(f"hipotecas: {ult} n={anual_out[ult]['numero']} medio={medio} €")


def fetch_ipv():
    series = datos_tabla(T_IPV, nult=200)
    got = pick(series, "comunitat valenciana", "general", "indice")
    if len(got) != 1:
        die(f"IPV {T_IPV}: esperaba 1 serie CV, hay {len(got)}")
    trim = trimestral(datos(got[0]))
    if len(trim) < 20:
        die(f"IPV: solo {len(trim)} trimestres; ¿cambió la tabla?")
    write_json("ipv.json", {
        "fuente": fuente_ine(T_IPV, "Índice de Precios de Vivienda, "
                                    "Comunitat Valenciana"),
        "nota": "El IPV solo baja a CCAA; se usa como evolución porcentual, "
                "no como nivel local. El INE rebasa el índice cada pocos años: "
                "los niveles no son comparables entre bases, las variaciones sí.",
        "tabla": T_IPV, "serie": got[0]["COD"], "trimestral": trim,
    })
    log(f"IPV: {len(trim)} trimestres, último {sorted(trim)[-1]}")


SECCION_RE = re.compile(r"castello de la plana seccion (\d{5})\.")
DISTRITO_RE = re.compile(r"castello de la plana distrito (\d{2})\.")

INDICADORES = {
    "renta neta media por persona": "renta_neta_persona",
    "renta neta media por hogar": "renta_neta_hogar",
    "renta bruta media por persona": "renta_bruta_persona",
    "renta bruta media por hogar": "renta_bruta_hogar",
}


def fetch_adrh():
    series = datos_tabla(T_ADRH, nult=30)
    muni, distritos, secciones = {}, {}, {}
    for s in series:
        n = norm(s["Nombre"])
        ind = next((k for t, k in INDICADORES.items() if t in n), None)
        if ind is None or "castello de la plana" not in n:
            continue
        anual = {str(p["Anyo"]): rnd(p["Valor"], 0) for p in datos(s)
                 if p.get("Valor") is not None}
        msec, mdis = SECCION_RE.search(n), DISTRITO_RE.search(n)
        if msec:
            cusec = "12040" + msec.group(1)
            for y, v in anual.items():
                secciones.setdefault(cusec, {}).setdefault(y, {})[ind] = v
        elif mdis:
            for y, v in anual.items():
                distritos.setdefault(mdis.group(1), {}).setdefault(y, {})[ind] = v
        # el INE pasó a nombrar el municipio "Castelló de la Plana/Castellón
        # de la Plana"; sin la variante bilingüe no se encuentra la serie
        elif re.search(r"castello de la plana(/castellon de la plana)?\.", n):
            for y, v in anual.items():
                muni.setdefault(y, {})[ind] = v

    if len(secciones) < 80:
        die(f"ADRH: solo {len(secciones)} secciones de Castelló; formato cambiado?")
    ult = sorted(muni)[-1] if muni else die("ADRH: sin serie municipal")
    rp = muni[ult].get("renta_neta_persona")
    if not rp or not (5000 <= rp <= 30000):
        die(f"ADRH: renta neta por persona implausible en {ult}: {rp}")

    src = fuente(
        "INE — Atlas de Distribución de Renta de los Hogares (ADRH)",
        f"https://www.ine.es/jaxiT3/Tabla.htm?t={T_ADRH}",
        url_datos=f"{BASE}/DATOS_TABLA/{T_ADRH}",
        nota="Renta media anual en €. Desfase de publicación ~2 años: citar "
             "siempre el año del dato.",
    )
    write_json("renta_adrh.json", {
        "fuente": src,
        "municipio": {"codigo": "12040", "nombre": "Castelló de la Plana",
                      "series": muni},
        "distritos": distritos,
    })
    write_json("mapa_renta.json", {
        "fuente": src,
        "municipio": "12040",
        "nota_codigos": "CUSEC de 10 dígitos (12040 + distrito + sección)",
        "secciones": secciones,
    })
    log(f"ADRH: municipio {ult} renta neta/persona = {rp} €; "
        f"{len(secciones)} secciones, {len(distritos)} distritos")


def fetch_irav():
    """IRAV: tope legal de actualización anual de alquileres (Ley 12/2023).
    Nacional, mensual desde enero de 2025."""
    series = datos_tabla(T_IRAV, nult=60)
    s = pick_one(series, "indice general", "variacion anual")
    mens = mensual(datos(s))
    ult = sorted(mens)[-1]
    if not (-2 <= mens[ult] <= 10):
        die(f"IRAV implausible en {ult}: {mens[ult]}")
    write_json("irav.json", {
        "fuente": fuente_ine(T_IRAV, "Índice de Referencia de Arrendamientos "
                                     "de Vivienda (IRAV)"),
        "serie": s["COD"],
        "nota": "Variación anual máxima aplicable a la actualización de rentas "
                "de contratos posteriores al 25/05/2023 (Ley 12/2023). "
                "Nacional, mensual.",
        "mensual": mens,
        "ultimo": {"periodo": ult, "pct": mens[ult]},
    })
    log(f"IRAV: último {ult} = {mens[ult]}%")


def main():
    fetch_ipc()
    fetch_compraventas()
    fetch_hipotecas()
    fetch_ipv()
    fetch_adrh()
    fetch_irav()
    log("fetch_ine: todo OK")


if __name__ == "__main__":
    main()
