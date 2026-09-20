"""Cartografía de secciones censales de Castelló ciudad para el mapa Leaflet.

Fuente: shapefile del seccionado censal del INE (1/1/2021) publicado en la
página de SERPAVI (proyección Web Mercator). Se filtra CUMUN=12040, se
simplifica con Douglas-Peucker (tolerancia en metros) y se convierte a
WGS84 -> data/secciones.geojson (y build_all lo copia a web/data/).
"""

import json
import math
import zipfile

import shapefile

from common import CACHE_DIR, CUMUN_CASTELLO, DATA_DIR, die, download, log

URL = "https://cdn.mivau.gob.es/portal-web-mivau/vivienda/serpavi/SECC_CE_20210101_INE_WM.zip"
ZIP = CACHE_DIR / "secciones_ine.zip"
SHP_BASE = CACHE_DIR / "SECC_CE_20210101_INE_WM"
TOLERANCIA_M = 4  # metros: imperceptible a escala de ciudad

# Secciones del municipio que NO se dibujan en el mapa: las islas Columbretes
# (09-001) están a ~50 km de la costa y, al entrar en el encuadre, dejaban la
# ciudad reducida a una mancha en una esquina. Sus datos siguen en los JSON.
SECCIONES_FUERA = {"1204009001"}

R = 6378137.0


def a_wgs84(x, y):
    lon = math.degrees(x / R)
    lat = math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)
    return round(lon, 6), round(lat, 6)


def douglas_peucker(puntos, tol):
    if len(puntos) < 3:
        return puntos
    (x1, y1), (x2, y2) = puntos[0], puntos[-1]
    dx, dy = x2 - x1, y2 - y1
    norma = math.hypot(dx, dy) or 1e-12
    imax, dmax = 0, 0.0
    for i in range(1, len(puntos) - 1):
        px, py = puntos[i]
        d = abs(dx * (y1 - py) - (x1 - px) * dy) / norma
        if d > dmax:
            imax, dmax = i, d
    if dmax <= tol:
        return [puntos[0], puntos[-1]]
    izq = douglas_peucker(puntos[:imax + 1], tol)
    der = douglas_peucker(puntos[imax:], tol)
    return izq[:-1] + der


def main():
    if not (SHP_BASE.with_suffix(".shp")).exists():
        download(URL, ZIP, min_bytes=10_000_000)
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(CACHE_DIR)
    sf = shapefile.Reader(str(SHP_BASE))
    campos = [f[0] for f in sf.fields[1:]]
    i_cusec, i_cumun = campos.index("CUSEC"), campos.index("CUMUN")

    features = []
    for sr in sf.iterShapeRecords():
        if sr.record[i_cumun] != CUMUN_CASTELLO:
            continue
        if sr.record[i_cusec] in SECCIONES_FUERA:
            continue
        shape = sr.shape
        partes = list(shape.parts) + [len(shape.points)]
        anillos = []
        for a, b in zip(partes, partes[1:]):
            puntos = list(shape.points[a:b])
            # anillo cerrado: DP degenera si el primer y el último punto
            # coinciden; se parte por el punto más alejado del inicio
            if len(puntos) > 3 and puntos[0] == puntos[-1]:
                x0, y0 = puntos[0]
                k = max(range(1, len(puntos) - 1),
                        key=lambda i: (puntos[i][0] - x0) ** 2 + (puntos[i][1] - y0) ** 2)
                simple = (douglas_peucker(puntos[:k + 1], TOLERANCIA_M)[:-1]
                          + douglas_peucker(puntos[k:], TOLERANCIA_M))
            else:
                simple = douglas_peucker(puntos, TOLERANCIA_M)
            if len(simple) >= 4:
                anillos.append([list(a_wgs84(x, y)) for x, y in simple])
        if not anillos:
            die(f"sección {sr.record[i_cusec]}: geometría vacía tras simplificar")
        features.append({
            "type": "Feature",
            "properties": {"CUSEC": sr.record[i_cusec]},
            "geometry": {"type": "Polygon", "coordinates": anillos},
        })

    if len(features) < 80:
        die(f"solo {len(features)} secciones de {CUMUN_CASTELLO}")
    geojson = {"type": "FeatureCollection",
               "nota": "Seccionado censal 1/1/2021, INE (via SERPAVI/MIVAU), "
                       f"simplificado a {TOLERANCIA_M} m",
               "features": features}
    destino = DATA_DIR / "secciones.geojson"
    destino.write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")
    log(f"escrito data/secciones.geojson: {len(features)} secciones, "
        f"{destino.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
