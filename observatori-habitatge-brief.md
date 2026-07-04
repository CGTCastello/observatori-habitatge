# Observatori de l'Habitatge de Castelló — Inventario de fuentes y brief para Claude Code

**Proyecto:** web estática de datos sobre vivienda, salarios y coste de vida en Castelló de la Plana y provincia, como herramienta de la campaña de CGT Castelló de cara a la movilización por la vivienda.

**Principio rector:** todos los datos provienen de fuentes públicas oficiales, citadas y enlazadas. La web debe poder defenderse ante cualquier fact-check. Actualización anual manual (enero), generación de datos automatizada mediante scripts.

---

## 1. Inventario de fuentes

### 1.1 Alquiler — precio real de contratos

**SERPAVI (Ministerio de Vivienda y Agenda Urbana)** — LA FUENTE PRINCIPAL
- URL: https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi
- Qué es: explotación de fuentes tributarias (declaraciones de arrendamiento). Datos de contratos REALES, no de oferta.
- Descarga: base de datos íntegra en Excel (XLSX), años 2011–2024. Enlace de descarga en la propia página ("BD Sistema Estatal Índices de Alquiler de Vivienda").
- Granularidad: nacional, CCAA, provincia, municipio, distrito y **sección censal**.
- Variables: renta media €/m²/mes, cuantía media €/mes, superficie media, con mediana, P25 y P75.
- Periodicidad: anual (publicación con ~1,5 años de desfase; el dato 2024 se publicó en 2026).
- Uso: serie histórica principal del alquiler en Castelló ciudad y provincia; mapa por secciones censales.

**Registro de fianzas GVA (dades obertes)**
- URL dataset: https://dadesobertes.gva.es/ — buscar "Registro de las fianzas de alquiler de viviendas" (hay un dataset por año; ejemplo 2026: dataset `616eec66-ccd8-493c-bcaf-1e6a51717903`, CSV "fianzas-depositadas-por-municipio.csv").
- Qué es: fianzas de alquiler depositadas ante la Generalitat. Dato censal de contratos firmados en la Comunitat.
- Granularidad: municipio. Periodicidad: anual (un dataset por ejercicio; descargar todos los años disponibles).
- Uso: número de contratos de alquiler firmados en Castelló ciudad por año (proxy de rotación/tensión del mercado). OJO: verificar si incluye importe medio o solo número e importe total de fianzas; ajustar el indicador a lo que haya.

**Precios de referencia GVA / Observatori de l'Hàbitat**
- URL: https://habitatge.gva.es/es/web/vivienda-y-calidad-en-la-edificacion/preus-de-referencia y visor del Institut Cartogràfic Valencià.
- Qué es: precio mediano €/m² por zonas a partir del Registro de Fianzas de la CV. Verificar vigencia y año de los datos antes de usar (la explotación original es de 2019; puede estar desactualizada).
- Uso: secundario/contextual.

**IRAV (INE)**
- Índice de Referencia de Arrendamientos de Vivienda, publicado por el INE desde enero de 2025, usado para actualizar contratos. Mensual.
- Uso: contextual, en la sección de "¿cuánto puede subir tu alquiler?" de la calculadora.

**Portales (Idealista / Fotocasa)** — precio de OFERTA
- URLs: https://www.idealista.com/sala-de-prensa/informes-precio-vivienda/ (informes mensuales de alquiler y venta, con dato por municipio y provincia) y https://www.fotocasa.es/indice/
- Qué es: €/m² de la oferta publicada. Sobreestima el mercado real pero es el dato más reciente que existe (mes en curso).
- Obtención: manual (copiar el dato de Castelló de la Plana del informe mensual) o scraping puntual. NO automatizar scraping en producción; introducir el dato a mano en el JSON.
- Uso: dato de "situación actual" en la portada, claramente etiquetado como precio de oferta y con fecha.

### 1.2 Compraventa

**INE — Estadística de Transmisiones de Derechos de la Propiedad (ETDP)**
- URL: https://www.ine.es (operación ETDP; API JSON del INE disponible: https://servicios.ine.es/wstempus/js/)
- Compraventas de viviendas inscritas, mensual, por provincia. Serie desde 2007.

**INE — Índice de Precios de Vivienda (IPV)**
- Trimestral, por CCAA (no provincial). Base para la evolución porcentual del precio de compra.

**MIVAU — Valor tasado de vivienda libre**
- URL: https://www.mivau.gob.es (Estadísticas > Vivienda y suelo > Precios). Trimestral, provincial y municipios >25.000 hab. Serie larga desde 1995: €/m² tasado en Castelló de la Plana.
- Uso: serie principal del precio de compra a nivel local.

**Colegio de Registradores — Estadística Registral Inmobiliaria**
- URL: https://www.registradores.org (sección Estadísticas). Trimestral, provincial: €/m² de compraventas escrituradas, % de compras por extranjeros, accesibilidad hipotecaria.
- Formato: PDF/Excel. Extraer los datos de la provincia de Castellón.

**INE — Estadística de Hipotecas**
- Mensual, provincial: número e importe medio de hipotecas constituidas sobre vivienda. Complementa la narrativa del acceso a la compra.

### 1.3 Salarios, renta e inflación

**AEAT — Mercado de Trabajo y Pensiones en las Fuentes Tributarias**
- URL: https://sede.agenciatributaria.gob.es/Sede/datosabiertos/catalogo/hacienda/Mercado_de_Trabajo_y_Pensiones_en_las_Fuentes_Tributarias.shtml
- Anual (dato 2024 ya publicado). Salario medio anual por provincia, tramos de salario (en múltiplos del SMI), sexo, edad. Censal, basado en el modelo 190.
- NOTA metodológica: el salario medio de esta fuente tiene sesgo a la baja (no ajusta por tiempo trabajado); el "Módulo salarial año completo" ofrece el salario equivalente a jornada completa. Usar el bloque adecuado según el mensaje y explicarlo en la nota metodológica de la web.

**AEAT — Estadística de los declarantes del IRPF por municipios**
- Misma sede, catálogo de estadísticas AEAT. Anual: renta bruta y disponible media por municipio (Castelló de la Plana y resto de municipios >1.000 declarantes de la provincia).
- Uso: dato de renta municipal y ranking provincial.

**INE — Atlas de Distribución de Renta de los Hogares (ADRH)**
- URL: https://www.ine.es/experimental/atlas/experimental_atlas.htm (ya estadística oficial). API JSON disponible.
- Anual (~2 años de desfase). Renta media por persona y hogar, por **sección censal**. Incluye Gini y distribución.
- Uso: mapa de renta por barrios de Castelló, cruzable con el mapa de alquiler SERPAVI por sección censal y con las VT.

**INE — IPC**
- API JSON del INE. Mensual, provincial (índice general provincia de Castellón). Serie larga.
- Uso: deflactar salarios (salario real), y dato de inflación acumulada para la calculadora.

**SMI** — serie del salario mínimo (Ministerio de Trabajo). Tabla estática pequeña, mantener a mano en JSON.

### 1.4 Desahucios

**CGPJ — Efecto de la crisis en los órganos judiciales**
- URL: https://www.poderjudicial.es/cgpj/es/Temas/Estadistica-Judicial/Estudios-e-Informes/Efecto-de-la-Crisis-en-los-organos-judiciales/
- Trimestral, por provincia (serie desde 2007): lanzamientos practicados, desglosados por causa (LAU/alquiler, ejecución hipotecaria, otros). El lanzamiento es el dato que corresponde a "desahucio".
- Además: fichero "Lanzamientos practicados por Partidos Judiciales 2013–2025" (Excel), que permite bajar al partido judicial de Castelló de la Plana.
- Base PC-AXIS del CGPJ para descarga estructurada.
- Uso: gráfico de desahucios acumulados y por causa en la provincia; dato del partido judicial en portada. Es el dato con más carga narrativa: tratarlo con rigor (explicar qué mide y qué no).

### 1.5 Vivienda turística

**INE — Medición del número de viviendas turísticas (estadística experimental)**
- URL: https://www.ine.es/experimental/viv_turistica/experimental_viv_turistica.htm
- Semestral (referencias mayo y noviembre desde el cambio de 2024). Por municipio: nº de VT, plazas y % sobre el parque de viviendas. Basado en scraping de plataformas con deduplicación.

**Turisme GVA — Registro de Turismo (dades obertes)**
- URL: https://dadesobertes.gva.es/es/dataset/tur-gestur-vt (y datasets anuales tipo "dades-turisme-habitatges-comunitat-valenciana-2025").
- Datos semanales del registro oficial; CSV con la lista individualizada de viviendas de uso turístico (municipio, e incluso dirección). Serie de datasets por año permite reconstruir la evolución de altas.
- Uso: evolución del nº de VT registradas en Castelló ciudad y municipios costeros de la provincia (Benicàssim, Orpesa, Peníscola…); comparación registro oficial vs estimación INE (la diferencia es en sí un dato: VT sin registrar).

### 1.6 Contexto sociodemográfico

- **INE Padrón continuo**: población de Castelló ciudad y provincia, anual.
- **INE Censo de Población y Viviendas 2021**: parque de viviendas, viviendas no principales, régimen de tenencia (propiedad/alquiler) por municipio y sección.
- **INE Encuesta Continua de Hogares / Censo**: tamaño medio del hogar (para pasar de renta por persona a por hogar).

---

## 2. Indicadores derivados (los que cuentan la historia)

Cada indicador se precalcula en el pipeline y se guarda en JSON. La web no calcula nada salvo la calculadora.

1. **Índice 100 (gráfico estrella de portada):** evolución desde 2015 (base 100) de: alquiler €/m² (SERPAVI Castelló ciudad), precio compra €/m² (MIVAU valor tasado), salario medio (AEAT provincia), IPC (provincia). Cuatro líneas, un mensaje.
2. **Tasa de esfuerzo:** (alquiler medio mensual Castelló ciudad, SERPAVI) / (salario medio mensual neto estimado, AEAT) × 100. Serie anual + comparación con el umbral del 30%. Documentar la estimación de neto (aplicar retención media aproximada, explicitada en metodología).
3. **Años de salario para comprar:** (precio medio vivienda 90 m² a valor tasado) / (salario medio anual bruto). Serie anual.
4. **Salario real:** salario medio AEAT deflactado con IPC provincial (base 2015). Muestra la pérdida de poder adquisitivo.
5. **Desahucios:** lanzamientos anuales en la provincia por causa (área apilada); acumulado desde 2013 como cifra destacada.
6. **Vivienda turística:** evolución de VT registradas (GVA) y estimadas (INE) en Castelló ciudad; % sobre parque de viviendas; top municipios de la provincia.
7. **Mapa por secciones censales de Castelló ciudad:** renta media (ADRH) + alquiler €/m² (SERPAVI). Dos capas conmutables sobre el mismo mapa.
8. **Contratos de alquiler firmados/año** (fianzas GVA): tendencia del mercado.

---

## 3. Especificación de la web (brief para Claude Code)

### 3.1 Arquitectura

- **Web 100% estática**: HTML + CSS + JS vanilla. Sin build obligatorio, sin frameworks de aplicación, sin backend. Debe funcionar abriendo `index.html` y servida desde cualquier hosting.
- Destino: subdirectorio `/observatori-habitatge/` dentro de cgtcastello.org (WordPress en el mismo servidor; se sube por FTP/SFTP fuera de WP, o se incrusta por iframe/plantilla en blanco — dejar ambas opciones viables: rutas relativas siempre).
- **Datos**: ficheros JSON estáticos en `/data/` (uno por fuente/indicador), generados por el pipeline. La web los carga con `fetch()` relativo. Como fallback para file:// y para rendimiento, permitir también un `data.js` que los inyecte inline.
- **Gráficos**: Chart.js (CDN o vendorizado en `/vendor/`; preferible vendorizado para no depender de terceros). Mapa de secciones censales: Leaflet + GeoJSON de secciones censales del INE (descargable de la cartografía del Censo), con capas de coropletas.
- **Rendimiento**: objetivo Lighthouse >90 en todo. Lazy-load de los gráficos por debajo del fold (IntersectionObserver). GeoJSON simplificado (mapshaper, tolerancia razonable) para que pese <500 KB.

### 3.2 Estructura de la página (one-page larga con anclas + calculadora)

1. **Hero**: titular contundente + 3-4 cifras clave grandes (tasa de esfuerzo actual, subida del alquiler desde 2015, pérdida de salario real, desahucios acumulados). Cada cifra con su fuente en pequeño.
2. **La calculadora** (arriba, es el gancho): ver 3.3.
3. **Bloque alquiler**: índice 100 + serie SERPAVI + dato de oferta actual (portales, etiquetado).
4. **Bloque salarios e inflación**: salario nominal vs real, distribución por tramos de SMI (AEAT).
5. **Bloque compra**: años de salario para comprar, serie de precio tasado, hipotecas.
6. **Bloque desahucios**.
7. **Bloque vivienda turística**.
8. **Mapa de la ciudad**: renta y alquiler por sección censal.
9. **Metodología y fuentes**: tabla completa de fuentes con enlaces, fecha del dato y notas metodológicas. Fecha de última actualización visible.
10. **CTA sindical**: bloque final enlazando a la campaña, afiliación y contacto de CGT Castelló.

### 3.3 Calculadora ("Quant et costa viure?")

- Inputs: salario neto mensual (slider + campo), alquiler o cuota mensual (campo), opcional: año en que se firmó el alquiler / año de referencia salarial.
- Outputs:
  - Tu tasa de esfuerzo (% del sueldo que va a vivienda), con semáforo respecto al 30% y comparación con la media local.
  - Días del mes que trabajas solo para pagar la vivienda.
  - Poder adquisitivo perdido: cuánto tendría que ser tu sueldo hoy para comprar lo mismo que en el año elegido (IPC provincial acumulado, constante en JS actualizable).
  - Años de tu salario íntegro para comprar la vivienda media en Castelló.
- Todo client-side, constantes en un único objeto `CONFIG` al inicio del JS con comentario de fecha y fuente de cada constante (para la actualización anual en 5 minutos).
- Botón de compartir (Web Share API + fallback copiar enlace) con el resultado en el texto: "Trabajo X días al mes solo para pagar mi vivienda".

### 3.4 Idiomas

- Bilingüe: **valencià como versión principal** (`/observatori-habitatge/`), castellano en `/observatori-habitatge/es/`. Misma estructura, textos en ficheros separados o páginas duplicadas (preferible duplicar HTML: más simple y mejor SEO que i18n por JS).
- `hreflang` recíproco entre ambas versiones + x-default a la valenciana, coherente con la política Polylang del resto del sitio.

### 3.5 SEO / GEO / AEO

- Title/meta description optimizados para "precio alquiler Castellón", "preu lloguer Castelló", "sueldo medio Castellón", etc.
- JSON-LD: `Dataset` para cada bloque de datos (con `distribution` apuntando a los JSON), `FAQPage` con 6-8 preguntas del tipo "¿Cuánto ha subido el alquiler en Castelló?", "¿Cuál es el sueldo medio en Castellón?" con respuestas con cifras concretas y año, y `Organization` de CGT Castelló como publisher.
- Cada cifra clave en HTML semántico plano (no solo dentro de canvas de Chart.js): las respuestas deben ser extraíbles por crawlers y LLMs. Añadir un bloque `<section>` de "Dades clau" en texto con todas las cifras y su fuente.
- OG image por idioma con la cifra estrella.
- `sitemap.xml` propio del subdirectorio y alta en Search Console tras publicar.

### 3.6 Diseño

- Identidad CGT: rojinegro (#E30613 aprox. y negro) sobre fondo claro para legibilidad de datos; tipografía de sistema o una sola webfont (p. ej. Inter) autoalojada.
- Estética de "observatorio de datos" sobria: las cifras son las protagonistas. Nada de stock photos.
- Accesibilidad AA: contraste, `aria-label` en gráficos, tabla de datos alternativa (details/summary) bajo cada gráfico.
- Responsive mobile-first: la mayoría del tráfico de campaña vendrá de redes sociales en móvil.

---

## 4. Pipeline de datos (scripts, ejecución manual)

Directorio `/scripts/` en Python 3, un script por fuente + un `build_all.py`:

- `fetch_serpavi.py`: descarga el XLSX de la BD SERPAVI, filtra Castelló de la Plana (INE 12040), provincia 12 y secciones censales de la ciudad → `data/alquiler_serpavi.json` y `data/mapa_alquiler.json`.
- `fetch_ine.py`: usa la API JSON del INE (wstempus) para IPC provincial, ETDP, hipotecas, IPV, ADRH por sección censal → varios JSON.
- `fetch_aeat.py`: descarga tablas de salarios (provincia) y renta municipal; si la AEAT no ofrece descarga estructurada, dejar CSV de entrada manual documentado.
- `fetch_cgpj.py`: descarga el Excel de lanzamientos por partido judicial y las series provinciales → `data/desahucios.json`.
- `fetch_vt.py`: CSVs de dades obertes GVA (todas las anualidades) + tabla municipal del INE experimental → `data/vivienda_turistica.json`.
- `manual_inputs.csv`: precios de oferta de portales, SMI, cualquier dato introducido a mano, con columnas fecha/valor/fuente/url.
- `build_all.py`: ejecuta todo, valida esquemas (que ningún JSON quede vacío o con NaN), calcula los indicadores derivados de la sección 2, escribe `data/meta.json` con la fecha de generación y la fecha del último dato de cada fuente (que la web muestra en la sección de metodología).
- Cada script debe fallar ruidosamente y NO sobrescribir el JSON bueno si la fuente cambió de formato.

---

## 5. Plan de fases

> **Fase 1 — Pipeline:** estructura del repo y scripts de `/scripts/` de la sección 4. Empezar por `fetch_serpavi.py` y `fetch_ine.py`. Ejecutar cada uno y validar muestra del JSON resultante con datos de Castelló antes de seguir. Si una URL de descarga ha cambiado, buscarla en la web oficial de la fuente, no inventar rutas.
>
> **Fase 2 — Indicadores:** cálculo de los 8 indicadores de la sección 2 en `build_all.py`, con tests básicos (valores en rangos plausibles definidos en el propio test). Generar `data/meta.json`.
>
> **Fase 3 — Web:** one-page de la sección 3.2 en valenciano con datos reales de los JSON, Chart.js vendorizado y la calculadora de 3.3. Mobile-first.
>
> **Fase 4 — Mapa, castellano y SEO:** mapa Leaflet de secciones censales, versión `/es/`, hreflang, JSON-LD (Dataset + FAQPage + Organization), OG images y sitemap.
>
> Restricciones globales: web 100% estática con rutas relativas, sin frameworks JS, sin llamadas a APIs externas en el navegador, accesibilidad AA, y cada cifra publicada debe llevar fuente y año. Los textos en valenciano se pasan a revisión antes de darlos por buenos.

---

## 6. Avisos metodológicos que la web debe incluir (sección Metodología)

- SERPAVI mide contratos declarados fiscalmente: es el mejor dato de alquiler real, pero llega con desfase; el dato de portales es de oferta y sobreestima.
- El salario medio AEAT (bloque estándar) infravalora el salario a jornada completa; indicar qué bloque se usa.
- Los lanzamientos del CGPJ miden desahucios ejecutados judicialmente, no todos los abandonos forzosos de vivienda.
- La estimación INE de VT (scraping de plataformas) y el registro GVA miden cosas distintas; la diferencia aproxima la oferta turística no registrada.
- Renta ADRH llega con ~2 años de desfase: indicar siempre el año del dato junto a cada cifra.

## 7. Tareas de Polo (no de Claude Code)

- Decidir el titular del hero y validar todos los textos en valenciano.
- Recoger a mano el dato mensual de portales para `manual_inputs.csv` antes del lanzamiento.
- Subir el resultado a cgtcastello.org, alta del sitemap en Search Console y Bing.
- Calendario: publicar con datos cerrados de 2025 unos meses antes de la campaña; refresco de `manual_inputs.csv` y regeneración la semana previa a la convocatoria.
