/* Constants de la calculadora "Quant et costa viure?"
   ACTUALITZACIÓ ANUAL: regenera el pipeline (build_all.py) i actualitza ací
   els valors marcats, amb la data i la font de cadascun. La resta de la web
   llig els JSON de data/ i no cal tocar-la. */

window.CONFIG = {
  // Lloguer mitjà (MEDIANA) de contractes reals a Castelló ciutat, €/mes.
  // Font: SERPAVI (MIVAU), vivenda col·lectiva, dada 2024 (descarregat 07/2026).
  LLOGUER_MEDIANA_MES: 500,
  ANY_LLOGUER: 2024,

  // Taxa d'esforç mitjana local (lloguer mediana / salari net mitjà estimat).
  // Font: elaboració pròpia SERPAVI + AEAT, dada 2024 (build 07/2026).
  TAXA_MITJANA_PCT: 32.9,

  // Preu de la vivenda tipus de 90 m²: valor taxat mitjà de Castelló ciutat.
  // Font: MIVAU valor taxat, mitjana anual 2025 = 1.338,7 €/m² (07/2026).
  PREU_M2_TAXAT: 1338.7,
  ANY_PREU: 2025,
  SUPERFICIE_TIPUS_M2: 90,

  // Salari mitjà brut anual de la província i net mensual estimat (x12 pagues).
  // Font: AEAT Mercat de Treball, dada 2024; net = brut x 0,79 (07/2026).
  SALARI_BRUT_ANUAL: 23117,
  SALARI_NET_MES: 1522,
  ANY_SALARI: 2024,

  // SMI mensual vigent (14 pagues). Font: RD 126/2026 (BOE 18/02/2026).
  SMI_MENSUAL: 1221,

  // IPC general de la província de Castelló, mitjana anual, base 2025=100.
  // Font: INE (taula 24081), descarregat 07/2026. Per a "poder adquisitiu".
  IPC_ANUAL: {
    2015: 77.62, 2016: 77.196, 2017: 78.656, 2018: 79.985, 2019: 80.432,
    2020: 80.257, 2021: 82.961, 2022: 90.81, 2023: 94.277, 2024: 96.702,
    2025: 100.0,
  },
  // Últim IPC mensual disponible (per a l'equivalència "a dia de hui").
  IPC_ULTIM: { etiqueta: "maig 2026", valor: 103.046 },
};
