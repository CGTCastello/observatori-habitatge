# Observatori de l'Habitatge de Castelló

Web estática de datos sobre vivienda, salarios y coste de vida en Castelló,
herramienta de la campaña de vivienda de CGT Castelló. Ver
`observatori-habitatge-brief.md` para el brief completo.

## Pipeline de datos

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch_serpavi.py   # alquiler real (MIVAU/SERPAVI)
.venv/bin/python scripts/fetch_ine.py       # IPC, compraventas, hipotecas, IPV, ADRH
```

Los scripts descargan de fuentes oficiales, validan rangos de plausibilidad y
escriben JSON en `data/` de forma atómica: si una fuente cambia de formato,
abortan sin tocar el JSON bueno anterior. Las descargas pesadas se cachean en
`scripts/cache/` (usar `--force` en fetch_serpavi para re-descargar).

La URL del XLSX de SERPAVI cambia con cada publicación anual: está en la
constante `XLSX_URL` de `scripts/fetch_serpavi.py`, con instrucciones para
actualizarla.

## Estado

- [x] Fase 1a: `fetch_serpavi.py`, `fetch_ine.py`
- [ ] Fase 1b: `fetch_cgpj.py`, `fetch_vt.py`, `fetch_aeat.py`, `manual_inputs.csv`
- [ ] Fase 2: indicadores derivados en `build_all.py` + `data/meta.json`
- [ ] Fase 3: web one-page en valenciano (Chart.js + calculadora)
- [ ] Fase 4: mapa Leaflet, versión /es/, SEO (JSON-LD, hreflang, sitemap)
