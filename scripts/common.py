"""Utilidades comunes del pipeline del Observatori de l'Habitatge.

Principios (ver brief, sección 4):
- Fallar ruidosamente: cualquier anomalía aborta con SystemExit != 0.
- No sobrescribir nunca un JSON bueno con datos malos: se valida antes de
  escribir y la escritura es atómica (fichero temporal + os.replace).
"""

import json
import math
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "scripts" / "cache"

# Algunas webs oficiales (MIVAU) devuelven 403 a user-agents no navegador.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Códigos INE de referencia del proyecto.
CPRO_CASTELLO = "12"
CUMUN_CASTELLO = "12040"


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def download(url, dest, force=False, min_bytes=1024):
    """Descarga url a dest (Path) con caché. Devuelve dest."""
    dest = Path(dest)
    if dest.exists() and not force:
        log(f"cache: {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"descargando {url}")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=300)
    if r.status_code != 200:
        die(f"HTTP {r.status_code} al descargar {url}")
    if len(r.content) < min_bytes:
        die(f"descarga sospechosamente pequeña ({len(r.content)} bytes): {url}")
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(r.content)
    os.replace(tmp, dest)
    log(f"guardado {dest.name} ({len(r.content) / 1e6:.1f} MB)")
    return dest


def get_json(url, retries=3):
    """GET de una API JSON (INE wstempus, dades obertes GVA...)."""
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            last = repr(e)
        time.sleep(2 * (i + 1))
    die(f"fallo tras {retries} intentos en {url}: {last}")


def _check_no_nan(obj, path="$"):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        die(f"valor no finito en {path}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _check_no_nan(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_no_nan(v, f"{path}[{i}]")


def write_json(name, obj):
    """Escritura atómica y validada de data/<name>. Nunca deja un JSON roto."""
    if not obj:
        die(f"{name}: objeto vacío, no se escribe")
    _check_no_nan(obj)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = DATA_DIR / name
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    os.replace(tmp, dest)
    log(f"escrito data/{name} ({dest.stat().st_size / 1024:.0f} KB)")


def fuente(nombre, url, nota=None, url_datos=None):
    """Bloque estándar de cita de fuente que llevan todos los JSON."""
    f = {"nombre": nombre, "url": url, "fecha_descarga": date.today().isoformat()}
    if url_datos:
        f["url_datos"] = url_datos
    if nota:
        f["nota"] = nota
    return f


def rnd(x, nd=2):
    """Redondeo tolerante: None si el valor viene vacío o no numérico."""
    if x is None or x == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return int(round(v)) if nd == 0 else round(v, nd)
