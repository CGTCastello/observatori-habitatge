# Observatori de l'Habitatge de Castelló

Web estática de datos sobre vivienda, salarios y coste de vida en Castelló,
herramienta de la campaña de vivienda de CGT Castelló. Ver
`observatori-habitatge-brief.md` para el brief completo.

## Pipeline de datos

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch_serpavi.py   # alquiler real (MIVAU/SERPAVI)
.venv/bin/python scripts/fetch_ine.py       # IPC, compraventas, hipotecas, IPV, ADRH
.venv/bin/python scripts/fetch_cgpj.py      # desahucios (lanzamientos CGPJ)
.venv/bin/python scripts/fetch_vt.py        # vivienda turística (GVA + INE)
.venv/bin/python scripts/fetch_aeat.py      # salarios y renta IRPF municipal
.venv/bin/python scripts/fetch_mivau.py     # valor tasado €/m² (precio compra)
.venv/bin/python scripts/fetch_fianzas.py   # fianzas GVA (contratos de alquiler/año)
.venv/bin/python scripts/build_all.py       # indicadores derivados + meta.json
```

`build_all.py --fetch` ejecuta antes todos los fetchers. Cada indicador tiene
un test de rango plausible (dict `RANGOS`): si un valor se sale, el build
aborta sin publicar nada.

`scripts/manual_inputs.csv` guarda los datos introducidos a mano (SMI, precios
de oferta de portales) con fuente y URL por fila.

Los scripts descargan de fuentes oficiales, validan rangos de plausibilidad y
escriben JSON en `data/` de forma atómica: si una fuente cambia de formato,
abortan sin tocar el JSON bueno anterior. Las descargas pesadas se cachean en
`scripts/cache/` (usar `--force` en fetch_serpavi para re-descargar).

La URL del XLSX de SERPAVI cambia con cada publicación anual: está en la
constante `XLSX_URL` de `scripts/fetch_serpavi.py`, con instrucciones para
actualizarla.

## Estado

- [x] Fase 1a: `fetch_serpavi.py`, `fetch_ine.py`
- [x] Fase 1b: `fetch_cgpj.py`, `fetch_vt.py`, `fetch_aeat.py`, `manual_inputs.csv`
- [x] Fase 2: indicadores derivados en `build_all.py` + `data/meta.json`
- [x] Fase 3: web one-page en valenciano (Chart.js + calculadora) — textos pendientes de revisión
- [ ] Fase 4: mapa Leaflet, versión /es/, SEO (JSON-LD, hreflang, sitemap)
