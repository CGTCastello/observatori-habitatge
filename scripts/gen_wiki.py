"""Genera la wiki markdown del Observatori (wiki/) para consulta en Obsidian.

Todo sale de data/*.json: al regenerar el pipeline, regenerar también la wiki
(build anual: build_all.py -> gen_wiki.py). Los ficheros de wiki/ se
sobrescriben SIEMPRE: no editarlos a mano (los apuntes personales, mejor en
notas aparte que enlacen a estas).

Páginas: Observatori (portada), Lloguer, Salaris, Compra, Desnonaments,
Vivenda turística, Renda i barris, Pensions, Metodologia y Municipis/…
Enlaces internos en formato [[wikilink]] de Obsidian.
"""

import json
import re
import unicodedata
from datetime import date

from common import DATA_DIR, ROOT, die, log

WIKI = ROOT / "wiki"
AVISO = ("> [!info] Generado por `scripts/gen_wiki.py` el {hoy} — no editar a "
         "mano: se sobrescribe con cada build.\n")


def slug(nombre):
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", " ", s).strip().replace(" ", "-")


def n0(v):
    """1234567.8 -> '1.234.568' (es). None -> 's.d.'"""
    if v is None:
        return "s.d."
    return f"{v:,.0f}".replace(",", ".")


def n1(v):
    if v is None:
        return "s.d."
    return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tabla(cabeceras, filas):
    out = ["| " + " | ".join(cabeceras) + " |",
           "|" + "|".join("---" for _ in cabeceras) + "|"]
    out += ["| " + " | ".join(str(c) for c in f) + " |" for f in filas]
    return "\n".join(out) + "\n"


def escribe(nombre, titulo, cuerpo, tags=("observatori",)):
    frontmatter = "---\ntags: [" + ", ".join(tags) + "]\n---\n"
    (WIKI / nombre).parent.mkdir(parents=True, exist_ok=True)
    (WIKI / nombre).write_text(
        frontmatter + f"# {titulo}\n\n" + AVISO.format(hoy=date.today().isoformat())
        + "\n" + cuerpo, encoding="utf-8")


def carga(nombre):
    p = DATA_DIR / nombre
    if not p.exists():
        die(f"falta data/{nombre}; ejecuta el pipeline antes de generar la wiki")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- portada
def pag_portada(ind, meta):
    te = ind["tasa_esfuerzo"]["serie"]
    u_te = sorted(te)[-1]
    i100 = ind["indice100"]["series"]
    u_alq = sorted(i100["alquiler_m2"])[-1]
    d = ind["desahucios"]
    sa = ind["subida_absorbida"]
    cuerpo = f"""Datos oficiales de vivienda, salarios y coste de vida en Castelló.
Versión wiki de la web del Observatori (CGT Castelló), generada de los mismos
JSON. Última actualización de datos: **{meta['generado'][:10]}**.

## Las cifras que resumen todo

- **{n1(te[u_te]['tasa_pct'])}%** del salario neto medio se va en el alquiler mediano ({u_te}) → [[Salaris]]
- El alquiler real ha subido un **+{n1(i100['alquiler_m2'][u_alq] - 100)}%** desde 2015 ({u_alq}) → [[Lloguer]]
- **{n0(d['acumulado']['total'])}** desahucios ejecutados en la provincia (2013–{d['acumulado']['hasta']}) → [[Desnonaments]]
- El **{d['resumen']['pct_lau']}%** de los desahucios de {d['resumen']['anyo']} fueron por alquiler → [[Desnonaments]]
- De cada 100 € de subida salarial neta ({sa['periodo']}), el alquiler se comió **{sa['pct_absorbido_neto']} €** → [[Salaris]]

## Páginas

- [[Lloguer]] — precio real de contratos, fianzas, comparativa provincial, IRAV
- [[Salaris]] — serie salarial, tramos SMI, esfuerzo por niveles y colectivos
- [[Compra]] — valor tasado, hipotecas, años de salario, entrada
- [[Desnonaments]] — lanzamientos por causa, provincia y partido judicial
- [[Vivenda turistica]] — registro GVA y estimación INE
- [[Renda i barris]] — ADRH por secciones, IRPF municipal, censo
- [[Pensions]] — pensión media y esfuerzo de alquiler
- [[Metodologia]] — qué mide cada fuente y cuándo se descargó
- [[Municipis/Index|Municipis]] — ficha por municipio de la provincia

## Material de formación

- Guion de sesión: `formacion/guion-sessio.md`
- Argumentario de réplicas: `formacion/argumentario.md`
- Fichas imprimibles (valencià): `formacion/fichas/`

## Regenerar

```bash
.venv/bin/python scripts/build_all.py --fetch   # datos nuevos
.venv/bin/python scripts/gen_wiki.py            # esta wiki
```
"""
    escribe("Observatori.md", "Observatori de l'Habitatge de Castelló", cuerpo)


# ---------------------------------------------------------------- lloguer
def pag_lloguer(alq, ind, fianzas, irav):
    m = alq["municipio"]["series"]
    anyos = [y for y in sorted(m) if "vc" in m[y]]
    filas = [[y, n0(m[y]["vc"]["eur_mes"]["p25"]), n0(m[y]["vc"]["eur_mes"]["mediana"]),
              n0(m[y]["vc"]["eur_mes"]["p75"]), n1(m[y]["vc"]["eur_m2"]["mediana"]),
              n0(m[y]["vc"].get("n"))] for y in anyos]
    comp = ind["comparativa_provincias"]["provincias"]
    anyos_c = sorted(comp["12"]["indice"])
    filas_c = [[y] + [n1(comp[c]["indice"].get(y)) for c in ("12", "46", "03")]
               for y in anyos_c]
    fi = fianzas["anual"]
    filas_f = [[y, n0(fi[y]["municipio"]["fianzas"]),
                n0(fi[y]["municipio"].get("importe_medio_eur")),
                n0(fi[y]["provincia"]["fianzas"]),
                "sí" if fi[y]["parcial"] else ""] for y in sorted(fi)]
    cuerpo = f"""Fuente principal: **SERPAVI** (MIVAU) — contratos reales declarados
fiscalmente, vivienda colectiva, estadístico = mediana. No confundir con
precios de oferta de portales (ver [[Metodologia]]).

## Castelló de la Plana — alquiler mensual de contratos reales

{tabla(["Año", "P25 €/mes", "Mediana €/mes", "P75 €/mes", "€/m²/mes", "Contratos testigo"], filas)}
La provincia en {anyos[-1]}: mediana {n1(alq['provincia']['series'][anyos[-1]]['vc']['eur_m2']['mediana'])} €/m² y {n0(alq['provincia']['series'][anyos[-1]]['vc']['eur_mes']['mediana'])} €/mes.

## Comparativa provincial (€/m², índice 2015 = 100)

{tabla(["Año", "Castelló", "València", "Alacant"], filas_c)}

## Contratos nuevos por año (fianzas GVA)

El importe medio de la fianza ≈ renta mensual de los contratos NUEVOS del año
(la fianza legal es una mensualidad): comparar con la mediana de arriba.

{tabla(["Año", "Contratos (ciudad)", "Fianza media €", "Contratos (provincia)", "Parcial"], filas_f)}

## ¿Cuánto puede subir un alquiler? (IRAV)

Último IRAV: **{n1(irav['ultimo']['pct'])}%** ({irav['ultimo']['periodo']}). Tope de
actualización anual para contratos posteriores al 25/05/2023 (Ley 12/2023).

Relacionado: [[Salaris]] (tasa de esfuerzo) · [[Municipis/Index|Municipis]]
"""
    escribe("Lloguer.md", "Lloguer", cuerpo)


# ---------------------------------------------------------------- salaris
def pag_salaris(sal, ind, desg):
    sr = ind["salario_real"]["serie"]
    filas = [[y, n0(sr[y]["nominal"]), n0(sr[y]["real_base_2015"])]
             for y in sorted(sr)]
    t = sal["tramos_smi"]
    acum = 0
    filas_t = []
    for k, v in t["tramos"].items():
        acum += v
        filas_t.append([k + " SMI", n0(v), n1(100 * v / t["asalariados_total"]),
                        n1(100 * acum / t["asalariados_total"])])
    niv = ind["esfuerzo_niveles"]
    filas_n = [[k, n0(v["bruto_anual"]), n0(v["neto_mes_estimado"]),
                n1(v["tasa_alquiler_mediano_pct"]), n1(v["tasa_alquiler_p25_pct"]),
                n1(v.get("pct_asalariados_hasta"))]
               for k, v in niv["niveles"].items()]
    ec = ind["esfuerzo_colectivos"]
    filas_c = []
    for grupo in ("edad", "sexo", "sectores"):
        for k, v in ec[grupo].items():
            # ingresos anuales marginales (menores de 18): la ratio no
            # significa nada, mejor fuera de la tabla
            if v["bruto_anual"] < 6000:
                continue
            filas_c.append([k, n0(v["bruto_anual"]), n0(v["neto_mes_estimado"]),
                            n1(v["tasa_alquiler_mediano_pct"]), n0(v["personas"])])
    filas_c.sort(key=lambda f: -float(f[3].replace(".", "").replace(",", ".")))
    sa = ind["subida_absorbida"]
    cuerpo = f"""Fuente: **AEAT, Mercado de Trabajo en las Fuentes Tributarias** (censal,
provincia). OJO: media de TODAS las relaciones laborales del año, sin ajuste
por jornada — infravalora el salario a jornada completa ([[Metodologia]]).

## Salario medio anual (nominal y real)

Real = deflactado con el IPC provincial, en euros de 2015.

{tabla(["Año", "Nominal €", "Real (€ de 2015)"], filas)}
Resumen {ind['salario_real']['resumen']['anyo']}: nominal **+{n1(ind['salario_real']['resumen']['subida_nominal_pct'])}%** y real **{'+' if ind['salario_real']['resumen']['variacion_real_pct'] >= 0 else ''}{n1(ind['salario_real']['resumen']['variacion_real_pct'])}%** desde 2015.

## ¿A dónde fue la subida? ({sa['periodo']})

- Subida del salario neto medio: **{n0(sa['subida_salario_neto_mes'])} €/mes** · subida del alquiler mediano: **{n0(sa['subida_alquiler_mes'])} €/mes**
- **El alquiler absorbió el {sa['pct_absorbido_neto']}% de la subida neta** (el {sa['pct_absorbido_bruto']}% de la bruta)

## Distribución por tramos de SMI ({t['anyo']})

{tabla(["Tramo", "Asalariados", "%", "% acumulado"], filas_t)}

## Tasa de esfuerzo por nivel salarial ({niv['anyo']})

Alquiler mediano {n0(niv['alquiler']['mediana'])} € · P25 {n0(niv['alquiler']['p25'])} €. Neto estimado con el modelo IRPF documentado.

{tabla(["Nivel", "Bruto anual €", "Neto/mes €", "% alquiler mediano", "% alquiler P25", "% asalariados hasta aquí"], filas_n)}

## Tasa de esfuerzo por colectivos ({ec['anyo']})

{ec['nota']}

{tabla(["Colectivo", "Bruto anual €", "Neto/mes €", "% del neto en alquiler", "Personas"], filas_c)}

Relacionado: [[Lloguer]] · [[Pensions]] · [[Compra]]
"""
    escribe("Salaris.md", "Salaris", cuerpo)


# ---------------------------------------------------------------- compra
def pag_compra(precio, hip, ind):
    pm = precio["municipio"]["anual"]
    apc = ind["anyos_para_comprar"]["serie"]
    filas = [[y, n1(pm.get(y)), n1(apc.get(y))] for y in sorted(pm)]
    ha = hip["anual"]
    filas_h = [[y, n0(ha[y]["numero"]), n0(ha[y]["importe_medio_eur"])]
               for y in sorted(ha)]
    ae = ind["ahorro_entrada"]
    cuerpo = f"""## Valor tasado y años de salario (Castelló ciudad)

Precio: valor tasado medio de vivienda libre (MIVAU), media anual. Años de
salario: vivienda de 90 m² sobre salario bruto medio AEAT.

{tabla(["Año", "€/m² tasado", "Años de salario (90 m²)"], filas)}

## Hipotecas constituidas sobre viviendas (provincia)

{tabla(["Año", "Hipotecas", "Importe medio €"], filas_h)}

## La entrada ({ae['anyo_precio']})

Entrada + gastos (30% del precio) = **{n0(ae['entrada_eur'])} €**. Años ahorrando el 15% del neto:

{tabla(["Nivel salarial", "Años"], [[k, n1(v)] for k, v in ae['anyos'].items()])}

Relacionado: [[Salaris]] · [[Lloguer]]
"""
    escribe("Compra.md", "Compra", cuerpo)


# ---------------------------------------------------------------- desnonaments
def pag_desnonaments(ind):
    d = ind["desahucios"]
    a = d["anual_por_causa"]
    filas = [[y, n0(a[y]["lau"]), n0(a[y]["ejecucion_hipotecaria"]),
              n0(a[y]["otros"]), n0(a[y]["total"]),
              n1(100 * a[y]["lau"] / a[y]["total"])] for y in sorted(a)]
    pj = d["partido_judicial"]
    filas_pj = [[y, n0(pj[y]["lau"]), n0(pj[y]["ejecucion_hipotecaria"]),
                 n0(pj[y]["otros"]), n0(pj[y]["total"])] for y in sorted(pj)]
    cuerpo = f"""Fuente: **CGPJ** — lanzamientos practicados (desahucios ejecutados con
intervención judicial). No incluye abandonos sin procedimiento: es el suelo
del problema, no el techo.

**Acumulado provincia 2013–{d['acumulado']['hasta']}: {n0(d['acumulado']['total'])} lanzamientos.**

## Provincia de Castellón, por causa

{tabla(["Año", "Alquiler (LAU)", "Ejec. hipotecaria", "Otros", "Total", "% LAU"], filas)}

## Partido judicial de Castelló de la Plana

{tabla(["Año", "Alquiler (LAU)", "Ejec. hipotecaria", "Otros", "Total"], filas_pj)}

Relacionado: [[Lloguer]] · [[Salaris]]
"""
    escribe("Desnonaments.md", "Desnonaments", cuerpo)


# ---------------------------------------------------------------- vivenda turística
def pag_vt(ind):
    vt = ind["vivienda_turistica"]
    ine = vt["castello"]["estimacion_ine"]
    filas = [[p, n0(ine[p].get("vt")), n0(ine[p].get("plazas")),
              n1(ine[p].get("pct_parque"))] for p in sorted(ine)]
    altas = vt["castello"]["registro_gva"]["altas_acumuladas"]
    filas_g = [[y, n0(v)] for y, v in altas.items() if y >= "2015"]
    filas_top = [[m["nombre"], n0(m["vt"]), n0(m["plazas"])]
                 for m in vt["top_municipios_gva"]]
    reg = vt["castello"]["registro_gva"]
    cuerpo = f"""Dos medidas distintas ([[Metodologia]]): el **registro GVA** (licencias
vigentes) y la **estimación INE** (anuncios reales en plataformas, semestral).

## Castelló ciudad — estimación INE

{tabla(["Periodo", "VT", "Plazas", "% del parque"], filas)}

## Castelló ciudad — registro GVA

Hoy: **{n0(reg['vt'])} VT registradas** ({n0(reg['plazas'])} plazas). Altas acumuladas
de las hoy vigentes (las bajas no aparecen):

{tabla(["Año de alta", "Acumulado"], filas_g)}

## Top municipios de la provincia (registro GVA)

{tabla(["Municipio", "VT", "Plazas"], filas_top)}

Relacionado: [[Municipis/Index|Municipis]] · [[Renda i barris]]
"""
    escribe("Vivenda turistica.md", "Vivenda turística", cuerpo)


# ---------------------------------------------------------------- renda i barris
def pag_renda(adrh, irpf, mapa_renta, censo, ind):
    ms = adrh["municipio"]["series"]
    filas = [[y, n0(ms[y].get("renta_neta_persona")), n0(ms[y].get("renta_neta_hogar"))]
             for y in sorted(ms)]
    u = sorted(ms)[-1]
    secs = mapa_renta["secciones"]
    con_dato = [(c, v[u]["renta_neta_persona"]) for c, v in secs.items()
                if u in v and "renta_neta_persona" in v[u]]
    con_dato.sort(key=lambda x: x[1])
    def sec_fmt(c, v):
        return [f"{c[5:7]}-{c[7:]}", n0(v)]
    filas_min = [sec_fmt(c, v) for c, v in con_dato[:5]]
    filas_max = [sec_fmt(c, v) for c, v in con_dato[-5:][::-1]]
    ranking = sorted(irpf["municipios"].items(),
                     key=lambda kv: -kv[1]["renta_bruta_media"])
    filas_r = [[i + 1, f"[[Municipis/{slug(m['nombre'])}|{m['nombre']}]]",
                n0(m["renta_bruta_media"]), n0(m["renta_disponible_media"]),
                n0(m["pos_nacional"])]
               for i, (c, m) in enumerate(ranking[:15])]
    ten = ind["censo"]["castello"]["tenencia"]
    cuerpo = f"""## Renta neta media, Castelló ciudad (ADRH, INE)

{tabla(["Año", "€/persona", "€/hogar"], filas)}

## Desigualdad por secciones censales ({u})

Las 5 secciones más pobres y más ricas por renta neta/persona (distrito-sección):

{tabla(["Sección", "€/persona"], filas_min)}
{tabla(["Sección", "€/persona"], filas_max)}

## Ranking municipal de renta (AEAT IRPF, {irpf['anyo']})

Top 15 de la provincia por renta bruta media por declaración:

{tabla(["#", "Municipio", "Renta bruta media €", "Renta disponible €", "Pos. estatal"], filas_r)}

## Parque y tenencia (Censo 2021)

Castelló ciudad: **{n0(ind['censo']['castello']['viviendas'])} viviendas**, el
**{n1(ind['censo']['castello']['pct_no_principales'])}% no principales**. De los
hogares: {n1(ten['pct_alquiler'])}% en alquiler, {n0(ten['propiedad'])} en propiedad.

Relacionado: [[Municipis/Index|Municipis]] · [[Lloguer]]
"""
    escribe("Renda i barris.md", "Renda i barris", cuerpo)


# ---------------------------------------------------------------- pensions
def pag_pensions(pen, ind):
    ec = ind["esfuerzo_colectivos"]["pensionistas"]
    filas = [[k.capitalize(), n0(pen[k]["pensionistas"]),
              n0(pen[k]["pension_media_anual_eur"]),
              n0(ec[k]["neto_mes_estimado"]),
              n1(ec[k]["tasa_alquiler_mediano_pct"])]
             for k in ("total", "varon", "mujer")]
    cuerpo = f"""Fuente: AEAT ({pen['anyo']}), provincia de Castellón. Neto estimado sin
cotización a la SS (modelo IRPF de [[Metodologia]]); tasa sobre el alquiler
mediano de Castelló ciudad.

{tabla(["", "Pensionistas", "Pensión media anual €", "Neta/mes €", "% en alquiler mediano"], filas)}

Relacionado: [[Salaris]] · [[Lloguer]]
"""
    escribe("Pensions.md", "Pensions", cuerpo)


# ---------------------------------------------------------------- metodologia
def pag_metodologia(meta):
    filas = [[v["nombre"], v["ultimo_dato"], v["fecha_descarga"]]
             for v in meta["fuentes"].values()]
    cuerpo = f"""Generado: {meta['generado']}. Pipeline reproducible en `scripts/`.

## Qué mide (y qué no) cada fuente

- **SERPAVI** explota declaraciones fiscales de arrendamiento: contratos
  reales, con ~1,5 años de desfase. Los portales miden oferta y sobreestiman.
- El **salario medio AEAT** promedia todas las relaciones laborales del año
  sin ajustar por jornada: infravalora el salario a jornada completa.
- El **neto estimado** usa cotización del trabajador (6,48%), gastos
  deducibles, reducción por rendimientos del trabajo y escala estatal
  duplicada (parámetros 2024): aproximación reproducible, no una nómina.
- Los **lanzamientos del CGPJ** son desahucios con intervención judicial.
- **VT**: el registro GVA (licencias) y la estimación INE (anuncios en
  plataformas) miden cosas distintas.
- La **renta ADRH** llega con ~2 años de desfase.
- El **Censo 2021** publica tenencia y tipo de vivienda solo a nivel
  municipal (el detalle por sección era del censo 2011).
- El **IRAV** limita la subida anual de contratos posteriores al 25/05/2023.

## Fuentes y actualidad

{tabla(["Fuente", "Último dato", "Descargado"], filas)}
"""
    escribe("Metodologia.md", "Metodologia", cuerpo)


# ---------------------------------------------------------------- municipis
def pag_municipis(municipios):
    indice = []
    for cod, m in sorted(municipios["municipios"].items(),
                         key=lambda kv: kv[1]["nombre"]):
        if "renta_irpf" not in m:
            continue
        nombre = m["nombre"]
        u = m.get("ultimo_anyo", "")
        alq = m.get("alquiler", {})
        lin = [f"Datos del municipio (código INE {cod}). Ver [[Municipis/Index|índice]]."]
        if alq.get(u):
            a = alq[u]
            lin += ["", f"## Alquiler real (SERPAVI, {u})", "",
                    f"- Mediana: **{n0(a['eur_mes'])} €/mes** · {n1(a['eur_m2'])} €/m²",
                    f"- Contratos testigo: {n0(a['n'])}"]
            if alq.get("2015", {}).get("eur_m2") and a.get("eur_m2"):
                lin.append(f"- Subida del €/m² desde 2015: "
                           f"**+{n0(100 * (a['eur_m2'] / alq['2015']['eur_m2'] - 1))}%**")
        f = m.get("fianzas", {})
        if f:
            uf = sorted(f)[-1]
            lin += ["", f"## Contratos nuevos (fianzas GVA, {uf})", "",
                    f"- **{n0(f[uf]['fianzas'])}** contratos · fianza media "
                    f"**{n0(f[uf].get('importe_medio_eur'))} €** (≈ renta de los nuevos)"]
        r = m["renta_irpf"]
        lin += ["", "## Renta IRPF (AEAT, 2023)", "",
                f"- Bruta media: **{n0(r['renta_bruta_media'])} €** "
                f"(mediana {n0(r['renta_bruta_mediana'])} €) · disponible "
                f"{n0(r['renta_disponible_media'])} €",
                f"- Posición estatal: {n0(r['pos_nacional'])}"]
        c = m.get("censo_2021")
        if c and c.get("pct_no_principales") is not None:
            lin += ["", "## Parque (Censo 2021)", "",
                    f"- {n0(c['viviendas'])} viviendas, "
                    f"**{n1(c['pct_no_principales'])}% no principales**"]
        vt = m.get("vt_gva")
        if vt:
            extra = ""
            if m.get("vt_ine", {}).get("vt") is not None:
                extra = (f" · estimadas INE: {n0(m['vt_ine']['vt'])} "
                         f"({m['vt_ine']['periodo']})")
            lin += ["", "## Vivienda turística", "",
                    f"- Registradas GVA: **{n0(vt['vt'])}**{extra}"]
        escribe(f"Municipis/{slug(nombre)}.md", nombre,
                "\n".join(lin) + "\n\nVer también: [[Lloguer]] · [[Renda i barris]]\n",
                tags=("observatori", "municipi"))
        indice.append(f"- [[Municipis/{slug(nombre)}|{nombre}]] — alquiler "
                      f"{n0(alq.get(u, {}).get('eur_mes'))} €/mes ({u})")
    escribe("Municipis/Index.md", "Municipis",
            "Una página por municipio >1.000 declarantes.\n\n"
            + "\n".join(indice) + "\n")
    return len(indice)


def main():
    ind = carga("indicadores.json")
    meta = carga("meta.json")
    WIKI.mkdir(exist_ok=True)
    for f in WIKI.rglob("*.md"):
        f.unlink()
    pag_portada(ind, meta)
    pag_lloguer(carga("alquiler_serpavi.json"), ind, carga("fianzas.json"),
                carga("irav.json"))
    pag_salaris(carga("salarios_aeat.json"), ind, carga("salarios_desglose.json"))
    pag_compra(carga("precio_vivienda.json"), carga("hipotecas.json"), ind)
    pag_desnonaments(ind)
    pag_vt(ind)
    pag_renda(carga("renta_adrh.json"), carga("renta_irpf_municipios.json"),
              carga("mapa_renta.json"), carga("censo_viviendas.json"), ind)
    pag_pensions(carga("pensiones.json"), ind)
    pag_metodologia(meta)
    n = pag_municipis(carga("municipios.json"))
    log(f"wiki generada: 9 páginas temáticas + {n} municipios en wiki/")


if __name__ == "__main__":
    main()
