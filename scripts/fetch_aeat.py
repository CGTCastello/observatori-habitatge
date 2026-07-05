"""AEAT — Mercado de Trabajo y Pensiones en las Fuentes Tributarias.

La AEAT no ofrece descarga estructurada de esta estadística, pero publica un
sitio estático por año con tablas HTML (páginas "jrubik" con nombres
hasheados que cambian cada edición). Navegamos por el texto de los enlaces:

  home.html -> Mapa web -> "Asalariados ... por provincia, edad y sexo"
    -> fila Castellón: nº de asalariados y salario medio anual (serie 2008+)
  y para el último año: "... por provincia, tramos de salario y sexo"
    -> una página por tramo de SMI -> fila Castellón.

-> data/salarios_aeat.json

NOTA metodológica (obligatoria en la web): el salario medio de esta fuente
promedia todas las relaciones laborales del año sin ajustar por tiempo
trabajado, por lo que infravalora el salario a jornada completa.
"""

import re
import unicodedata

from common import die, fuente, log, rnd, write_json
import requests

from common import UA

CATALOGO = ("https://sede.agenciatributaria.gob.es/Sede/datosabiertos/catalogo/"
            "hacienda/Mercado_de_Trabajo_y_Pensiones_en_las_Fuentes_Tributarias.shtml")
BASE = ("https://sede.agenciatributaria.gob.es/AEAT/Contenidos_Comunes/"
        "La_Agencia_Tributaria/Estadisticas/Publicaciones/sites/mercado")
ANYO_INICIO = 2008

LINK_RE = re.compile(r'href="([^"]+)"[^>]*>((?:[^<]|<[^a][^>]*>)*?)</a>', re.S)
# "Castell[^<]*" tolera ó en utf-8, latin-1 o &oacute; según la edición;
# el <div> interior cambia de atributos entre ediciones (depth_div_2 vs style)
ROW_RE = re.compile(
    r"<th[^>]*>\s*<div[^>]*>\s*Castell[^<]*</div>\s*</th>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>([^<]*)</td>")


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def get(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    if r.status_code != 200:
        return None
    # las ediciones modernas son UTF-8 sin charset en la cabecera; las
    # antiguas, latin-1: decodificar a mano para no heredar mojibake
    try:
        return r.content.decode("utf-8")
    except UnicodeDecodeError:
        return r.content.decode("latin-1")


def links(html):
    """[(href, texto_normalizado)] de todos los <a> de la página."""
    out = []
    for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        text = norm(re.sub(r"<[^>]+>", " ", m.group(2)))
        out.append((m.group(1), text))
    return out


def link_por_texto(html, contiene, url_base):
    for href, text in links(html):
        if contiene in text:
            return f"{url_base}/{href}"
    return None


def num_es(s):
    s = s.strip().replace("&nbsp;", "")
    if not s or s in ("..", "-", "s.e."):
        return None
    return float(s.replace(".", "").replace(",", "."))


def fila_castellon(html):
    """[valores] de la fila provincial de Castellón en la tabla jrubik."""
    m = ROW_RE.search(html)
    if not m:
        return None
    return [num_es(c) for c in CELL_RE.findall(m.group(1))]


def tabla_de_anyo(anyo, texto_tabla):
    """URL de la tabla cuyo título contiene texto_tabla, para un año dado."""
    url_base = f"{BASE}/{anyo}"
    home = get(f"{url_base}/home.html")
    if home is None:
        return None, url_base
    mapa_href = next((h for h, t in links(home)
                      if h.startswith("mapa") and h.endswith(".html")), None)
    if not mapa_href:
        return None, url_base
    mapa = get(f"{url_base}/{mapa_href}")
    if mapa is None:
        return None, url_base
    return link_por_texto(mapa, texto_tabla, url_base), url_base


def fetch_serie_salarios():
    serie = {}
    for anyo in range(ANYO_INICIO, 2100):
        url, _ = tabla_de_anyo(anyo, "por provincia, edad y sexo")
        if url is None:
            if anyo <= 2024:  # ediciones que sabemos publicadas
                log(f"aviso: edición {anyo} no encontrada")
                continue
            break
        html = get(url)
        vals = fila_castellon(html) if html else None
        if not vals or len(vals) < 4 or vals[0] is None or vals[3] is None:
            log(f"aviso: sin fila de Castellón en {anyo} ({url})")
            continue
        # columnas: Asalariados | Percepciones/asal. | Salarios | Salario medio
        serie[str(anyo)] = {"asalariados": int(vals[0]),
                            "salario_medio_eur": rnd(vals[3], 0)}
        log(f"{anyo}: {int(vals[0])} asalariados, salario medio {vals[3]:.0f} €")
    if len(serie) < 10:
        die(f"solo {len(serie)} años de salarios; ¿cambió el formato del sitio?")
    ult = sorted(serie)[-1]
    sm = serie[ult]["salario_medio_eur"]
    if not (12_000 <= sm <= 45_000):
        die(f"salario medio {ult} implausible: {sm}")
    return serie


def fetch_tramos(anyo):
    url, url_base = tabla_de_anyo(anyo, "por provincia, tramos de salario")
    if url is None:
        die(f"no encuentro la tabla de tramos de {anyo}")
    html = get(url)
    tramo_links = [(h, t) for h, t in links(html) if "smi" in t]
    if len(tramo_links) < 10:
        die(f"solo {len(tramo_links)} tramos SMI; ¿cambió la estructura?")
    tramos, total_tramos = {}, 0
    for href, text in tramo_links:
        page = get(f"{url_base}/{href}")
        vals = fila_castellon(page) if page else None
        if not vals or vals[0] is None:
            die(f"tramo {text!r}: sin fila de Castellón")
        etiqueta = text.replace("de ", "", 1).replace(" smi", "")
        tramos[etiqueta] = int(vals[0])
        total_tramos += int(vals[0])
    # el total de la página principal (tramo Total) valida la suma
    vals_total = fila_castellon(html)
    if vals_total and vals_total[0] and abs(total_tramos - vals_total[0]) > vals_total[0] * 0.01:
        die(f"tramos no cuadran: suma {total_tramos} vs total {vals_total[0]}")
    return {"anyo": str(anyo), "asalariados_total": int(vals_total[0]),
            "tramos": tramos,
            "etiquetas": "límites en múltiplos del SMI del año de referencia"}


FILA_NOMBRE_RE = re.compile(
    r"<th[^>]*>\s*<div[^>]*>([^<]+)</div>\s*</th>(.*?)</tr>", re.S)


def menu_items(html, menu):
    """Elementos del desplegable `menu` de una página jrubik: pares
    (href, texto) del bloque <ul aria-label="menu" role="menu">."""
    bloque = re.search(
        r'<ul[^>]*aria-label="' + re.escape(menu) + r'"[^>]*role="menu"(.*?)</ul>',
        html, re.S)
    if not bloque:
        return []
    return [(m.group(1), m.group(2).strip()) for m in
            re.finditer(r'href="([^"#]+)"[^>]*role="menuitem"[^>]*>([^<]+)',
                        bloque.group(1))]


def filas_tabla(html):
    """Todas las filas (nombre, [valores]) de una tabla jrubik."""
    return [(m.group(1).strip(), [num_es(c) for c in CELL_RE.findall(m.group(2))])
            for m in FILA_NOMBRE_RE.finditer(html)]


def fetch_desglose(anyo):
    """Asalariados y salario medio de Castellón por edad, sexo y sector."""
    out = {"anyo": str(anyo), "edad": {}, "sexo": {}, "sectores": {}}

    url, url_base = tabla_de_anyo(anyo, "por provincia, edad y sexo")
    if url is None:
        die(f"desglose: no encuentro la tabla de edad de {anyo}")
    html = get(url)
    for menu, clave in [("Tramos de Edad", "edad"), ("Sexo", "sexo")]:
        for href, texto in menu_items(html, menu):
            if norm(texto) == "total":
                continue
            vals = fila_castellon(get(f"{url_base}/{href}") or "")
            if not vals or vals[0] is None or vals[3] is None:
                log(f"aviso: sin dato de {texto!r}")
                continue
            out[clave][texto] = {"asalariados": int(vals[0]),
                                 "salario_medio_eur": rnd(vals[3], 0)}

    url, url_base = tabla_de_anyo(anyo, "sector de actividad (nace), provincia")
    if url is None:
        die(f"desglose: no encuentro la tabla de sectores de {anyo}")
    html_sect = get(url)
    href_cast = next((h for menu in ("Comunitat Valenciana", "Provincia")
                      for h, t in menu_items(html_sect, menu)
                      if norm(t).startswith("castell")), None)
    if href_cast is None:
        die("desglose: Castellón no está en el menú de provincias")
    for nombre, vals in filas_tabla(get(f"{url_base}/{href_cast}")):
        if len(vals) >= 4 and vals[0] and vals[3] and norm(nombre) != "total":
            out["sectores"][nombre] = {"asalariados": int(vals[0]),
                                       "salario_medio_eur": rnd(vals[3], 0)}
    if len(out["edad"]) < 5 or len(out["sexo"]) != 2 or len(out["sectores"]) < 8:
        die(f"desglose incompleto: {len(out['edad'])} edades, "
            f"{len(out['sexo'])} sexos, {len(out['sectores'])} sectores")
    return out


def fetch_pensiones(anyo):
    """Pensionistas y pensión media anual de la provincia (total/varón/mujer)."""
    url, _ = tabla_de_anyo(anyo, "pensiones medias por sexo, provincia del "
                                 "perceptor y edad")
    if url is None:
        die(f"pensiones: no encuentro la tabla de {anyo}")
    vals = fila_castellon(get(url) or "")
    # 3 bloques (Total/Varón/Mujer) × (pensionistas, pensiones/perceptor, media)
    if not vals or len(vals) < 9:
        die(f"pensiones: fila inesperada {vals}")
    bloques = {}
    for i, sexo in enumerate(["total", "varon", "mujer"]):
        n, media = vals[i * 3], vals[i * 3 + 2]
        if n is None or media is None or not (5000 <= media <= 40000):
            die(f"pensiones {sexo}: valores implausibles {n}, {media}")
        bloques[sexo] = {"pensionistas": int(n), "pension_media_anual_eur": rnd(media, 0)}
    return {"anyo": str(anyo), **bloques}


CATALOGO_IRPF = ("https://sede.agenciatributaria.gob.es/Sede/datosabiertos/"
                 "catalogo/hacienda/Estadistica_de_los_declarantes_del_IRPF_"
                 "por_municipios.shtml")
BASE_IRPF = ("https://sede.agenciatributaria.gob.es/AEAT/Contenidos_Comunes/"
             "La_Agencia_Tributaria/Estadisticas/Publicaciones/sites/irpfmunicipios")
FILA_MUNI_RE = re.compile(
    r"<th[^>]*>\s*<div[^>]*>([^<]*-12\d{3})</div>\s*</th>(.*?)</tr>", re.S)

# columnas de la tabla "Posicionamiento de los municipios >1.000 hab"
CAMPOS_IRPF = ["titulares", "declaraciones", "habitantes", "pos_nacional",
               "pos_autonomico", "renta_bruta_media", "renta_bruta_mediana",
               "renta_disponible_media", "renta_disponible_mediana"]


def fetch_renta_municipal():
    """Renta IRPF de los municipios >1.000 hab de la provincia (último año)."""
    anyo, url = None, None
    for a in range(2026, 2018, -1):
        url, url_base = None, f"{BASE_IRPF}/{a}"
        home = get(f"{url_base}/home.html")
        if home is None:
            continue
        mapa_href = next((h for h, t in links(home)
                          if h.startswith("mapa") and h.endswith(".html")), None)
        mapa = get(f"{url_base}/{mapa_href}") if mapa_href else None
        url = link_por_texto(mapa, "posicionamiento de los municipios mayores",
                             url_base) if mapa else None
        if url:
            anyo = a
            break
    if not url:
        die("IRPF municipios: no encuentro la tabla de posicionamiento")
    html = get(url)
    munis = {}
    for m in FILA_MUNI_RE.finditer(html):
        etiqueta, celdas = m.group(1), [num_es(c) for c in CELL_RE.findall(m.group(2))]
        nombre, _, cod = etiqueta.rpartition("-")
        if len(celdas) != len(CAMPOS_IRPF):
            die(f"IRPF municipios: {etiqueta}: {len(celdas)} columnas, "
                f"esperaba {len(CAMPOS_IRPF)}")
        munis[cod] = {"nombre": nombre.split("/")[-1].strip(),
                      **{k: int(v) if v is not None else None
                         for k, v in zip(CAMPOS_IRPF, celdas)}}
    if "12040" not in munis or len(munis) < 30:
        die(f"IRPF municipios: {len(munis)} municipios y "
            f"Castelló {'presente' if '12040' in munis else 'AUSENTE'}")
    rb = munis["12040"]["renta_bruta_media"]
    if not (15_000 <= rb <= 60_000):
        die(f"IRPF municipios: renta bruta media implausible {rb}")
    log(f"IRPF municipios {anyo}: {len(munis)} municipios de la provincia; "
        f"Castelló ciudad renta bruta media {rb} € (pos. estatal "
        f"{munis['12040']['pos_nacional']})")
    return str(anyo), munis


def main():
    serie = fetch_serie_salarios()
    ult = sorted(serie)[-1]
    tramos = fetch_tramos(int(ult))
    desglose = fetch_desglose(int(ult))
    write_json("salarios_desglose.json", {
        "fuente": fuente(
            "AEAT — Mercado de Trabajo y Pensiones en las Fuentes Tributarias",
            CATALOGO,
            nota="Asalariados y salario medio anual bruto de la provincia de "
                 "Castellón por tramo de edad, sexo y sector NACE. Sin ajuste "
                 "por jornada ni tiempo trabajado.",
        ),
        **desglose,
    })
    log(f"desglose {ult}: {len(desglose['edad'])} edades, "
        f"{len(desglose['sectores'])} sectores")
    pensiones = fetch_pensiones(int(ult))
    write_json("pensiones.json", {
        "fuente": fuente(
            "AEAT — Mercado de Trabajo y Pensiones en las Fuentes Tributarias",
            CATALOGO,
            nota="Pensionistas y pensión media anual (todas las pensiones "
                 "percibidas) de la provincia de Castellón.",
        ),
        **pensiones,
    })
    log(f"pensiones {ult}: media {pensiones['total']['pension_media_anual_eur']} € "
        f"({pensiones['total']['pensionistas']} pensionistas)")
    anyo_irpf, munis_irpf = fetch_renta_municipal()
    write_json("renta_irpf_municipios.json", {
        "fuente": fuente(
            "AEAT — Estadística de los declarantes del IRPF por municipios",
            CATALOGO_IRPF,
            nota="Municipios >1.000 habitantes de la provincia de Castellón. "
                 "Rentas medias/medianas por declaración, en €. pos_nacional/"
                 "pos_autonomico = puesto por renta bruta media.",
        ),
        "anyo": anyo_irpf,
        "municipios": munis_irpf,
    })
    write_json("salarios_aeat.json", {
        "fuente": fuente(
            "AEAT — Mercado de Trabajo y Pensiones en las Fuentes Tributarias",
            CATALOGO,
            nota="Salario medio anual bruto por perceptor (todas las relaciones "
                 "laborales del año, sin ajuste por tiempo trabajado: "
                 "infravalora el salario a jornada completa). Provincia de "
                 "Castellón. Fuente censal: modelo 190.",
        ),
        "provincia": "Castellón",
        "serie": serie,
        "tramos_smi": tramos,
    })
    log(f"OK: serie {sorted(serie)[0]}-{ult}; salario medio {ult}: "
        f"{serie[ult]['salario_medio_eur']} €")


if __name__ == "__main__":
    main()
