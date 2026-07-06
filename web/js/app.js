/* Observatori de l'Habitatge de Castelló — lògica de la web.
   Vanilla JS. Les dades venen dels JSON de data/ (o de data/data.js quan
   s'obri amb file://). Els gràfics es creen en fer-se visibles
   (IntersectionObserver) per a no bloquejar la càrrega. */

(function () {
  "use strict";

  var ROIG = "#e30613", NEGRE = "#1a1a1a", GRIS = "#8a8a8a",
      BLAU = "#25567a", TARONJA = "#c96a00", VERD = "#1a7a3c";
  var FMT = new Intl.NumberFormat("ca-ES", { maximumFractionDigits: 1 });
  var FMT0 = new Intl.NumberFormat("ca-ES", { maximumFractionDigits: 0 });

  // ---------- càrrega de dades ----------
  var FITXERS = ["indicadores", "alquiler_serpavi", "salarios_aeat",
                 "precio_vivienda", "hipotecas", "meta"];

  function carrega(nom) {
    return fetch("data/" + nom + ".json").then(function (r) {
      if (!r.ok) throw new Error(nom + ": HTTP " + r.status);
      return r.json();
    });
  }

  function carregaTot() {
    if (window.OBSERVATORI_DADES) {
      return Promise.resolve(window.OBSERVATORI_DADES);
    }
    var dades = {};
    return Promise.all(FITXERS.map(function (n) {
      return carrega(n).then(function (d) { dades[n] = d; });
    })).then(function () { return dades; });
  }

  // ---------- utilitats ----------
  function anysOrdenats(obj) { return Object.keys(obj).sort(); }

  function taulaAccessible(figura, capcaleres, files) {
    var det = figura.querySelector("details.taula");
    if (!det) return;
    var html = "<table><thead><tr>";
    capcaleres.forEach(function (c) { html += "<th scope='col'>" + c + "</th>"; });
    html += "</tr></thead><tbody>";
    files.forEach(function (f) {
      html += "<tr>" + f.map(function (v, i) {
        return (i ? "<td>" : "<th scope='row'>") + (v == null ? "–" : v) +
               (i ? "</td>" : "</th>");
      }).join("") + "</tr>";
    });
    det.insertAdjacentHTML("beforeend", html + "</tbody></table>");
  }

  var pendents = {};   // id de canvas -> funció que crea el gràfic
  var observador = new IntersectionObserver(function (entrades) {
    entrades.forEach(function (e) {
      if (e.isIntersecting && pendents[e.target.id]) {
        pendents[e.target.id]();
        delete pendents[e.target.id];
        observador.unobserve(e.target);
      }
    });
  }, { rootMargin: "150px" });

  function grafic(id, crea) {
    var canvas = document.getElementById(id);
    if (!canvas) return;
    pendents[id] = function () { crea(canvas); };
    observador.observe(canvas);
  }

  var OPCIONS_BASE = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: NEGRE, boxWidth: 14, usePointStyle: true } },
    },
    scales: {
      x: { ticks: { color: GRIS }, grid: { display: false } },
      y: { ticks: { color: GRIS }, grid: { color: "#eee" } },
    },
  };

  function fusiona(extra) {
    return Object.assign({}, JSON.parse(JSON.stringify(OPCIONS_BASE)), extra || {});
  }

  // ---------- gràfics ----------
  function iniciaGrafics(dades) {
    var ind = dades.indicadores;

    // 1. Índex 100
    grafic("grafIndex100", function (cv) {
      var s = ind.indice100.series;
      var anys = anysOrdenats(s.ipc);  // la sèrie més llarga fins a l'últim any complet
      var defs = [
        ["Lloguer €/m² (SERPAVI)", s.alquiler_m2, ROIG, 3],
        ["Preu compra €/m² (taxat)", s.compra_m2, TARONJA, 2],
        ["Salari mitjà (AEAT)", s.salario, BLAU, 2],
        ["IPC província", s.ipc, GRIS, 2],
      ];
      new Chart(cv, {
        type: "line",
        data: {
          labels: anys,
          datasets: defs.map(function (d) {
            return { label: d[0], data: anys.map(function (a) { return d[1][a] || null; }),
                     borderColor: d[2], backgroundColor: d[2], borderWidth: d[3],
                     pointRadius: 2, spanGaps: true };
          }),
        },
        options: fusiona(),
      });
      taulaAccessible(cv.closest("figure"),
        ["Any", "Lloguer", "Compra", "Salari", "IPC"],
        anys.map(function (a) {
          return [a, s.alquiler_m2[a], s.compra_m2[a], s.salario[a], s.ipc[a]];
        }));
    });

    // 2. Lloguer: mediana i rang P25-P75 (€/mes)
    grafic("grafLloguer", function (cv) {
      var series = dades.alquiler_serpavi.municipio.series;
      var anys = anysOrdenats(series).filter(function (a) { return series[a].vc; });
      function v(a, k) { return series[a].vc.eur_mes[k]; }
      new Chart(cv, {
        type: "line",
        data: {
          labels: anys,
          datasets: [
            { label: "P75 (25% més car)", data: anys.map(function (a) { return v(a, "p75"); }),
              borderColor: "rgba(227,6,19,.25)", backgroundColor: "rgba(227,6,19,.12)",
              fill: "+2", pointRadius: 0, borderWidth: 1 },
            { label: "Mediana", data: anys.map(function (a) { return v(a, "mediana"); }),
              borderColor: ROIG, backgroundColor: ROIG, borderWidth: 3, pointRadius: 2 },
            { label: "P25 (25% més barat)", data: anys.map(function (a) { return v(a, "p25"); }),
              borderColor: "rgba(227,6,19,.25)", backgroundColor: "rgba(227,6,19,.12)",
              pointRadius: 0, borderWidth: 1 },
          ],
        },
        options: fusiona(),
      });
      taulaAccessible(cv.closest("figure"), ["Any", "P25 €/mes", "Mediana €/mes", "P75 €/mes", "Contractes testimoni"],
        anys.map(function (a) {
          return [a, v(a, "p25"), v(a, "mediana"), v(a, "p75"), series[a].vc.n];
        }));
    });

    // 2b. Comparativa provincial (índex 100 del €/m²)
    grafic("grafComparativa", function (cv) {
      var comp = ind.comparativa_provincias.provincias;
      var defs = [["12", ROIG, 3], ["46", NEGRE, 2], ["03", GRIS, 2]];
      var anys = anysOrdenats(comp["12"].indice);
      new Chart(cv, {
        type: "line",
        data: {
          labels: anys,
          datasets: defs.map(function (d) {
            var p = comp[d[0]];
            return { label: p.nombre.split("/")[0], data: anys.map(function (a) { return p.indice[a]; }),
                     borderColor: d[1], backgroundColor: d[1], borderWidth: d[2],
                     pointRadius: 2 };
          }),
        },
        options: fusiona(),
      });
      taulaAccessible(cv.closest("figure"),
        ["Any"].concat(defs.map(function (d) { return comp[d[0]].nombre.split("/")[0] + " €/m²"; })),
        anys.map(function (a) {
          return [a].concat(defs.map(function (d) { return comp[d[0]].eur_m2[a]; }));
        }));
    });

    // 3. Taxa d'esforç
    grafic("grafEsforc", function (cv) {
      var s = ind.tasa_esfuerzo.serie;
      var anys = anysOrdenats(s);
      new Chart(cv, {
        type: "line",
        data: {
          labels: anys,
          datasets: [
            { label: "% del salari net per a llogar", data: anys.map(function (a) { return s[a].tasa_pct; }),
              borderColor: ROIG, backgroundColor: ROIG, borderWidth: 3, pointRadius: 2 },
            { label: "Llindar del 30% (sobrecàrrega)", data: anys.map(function () { return 30; }),
              borderColor: NEGRE, borderDash: [6, 4], pointRadius: 0, borderWidth: 1.5 },
          ],
        },
        options: fusiona(),
      });
      taulaAccessible(cv.closest("figure"), ["Any", "Lloguer €/mes", "Salari net €/mes", "Taxa %"],
        anys.map(function (a) {
          return [a, s[a].alquiler_mes, s[a].salario_neto_mes, s[a].tasa_pct];
        }));
    });

    // 4. Salari nominal vs real
    grafic("grafSalaris", function (cv) {
      var s = ind.salario_real.serie;
      var anys = anysOrdenats(s);
      new Chart(cv, {
        type: "line",
        data: {
          labels: anys,
          datasets: [
            { label: "Salari mitjà nominal €/any", data: anys.map(function (a) { return s[a].nominal; }),
              borderColor: BLAU, backgroundColor: BLAU, borderWidth: 2, pointRadius: 2 },
            { label: "Salari real (€ de 2015)", data: anys.map(function (a) { return s[a].real_base_2015; }),
              borderColor: ROIG, backgroundColor: ROIG, borderWidth: 3, pointRadius: 2 },
          ],
        },
        options: fusiona(),
      });
      taulaAccessible(cv.closest("figure"), ["Any", "Nominal €", "Real (€ de 2015)"],
        anys.map(function (a) { return [a, s[a].nominal, s[a].real_base_2015]; }));
    });

    // 5. Distribució per trams d'SMI
    grafic("grafTrams", function (cv) {
      var t = dades.salarios_aeat.tramos_smi;
      var etiquetes = Object.keys(t.tramos);
      var total = t.asalariados_total;
      new Chart(cv, {
        type: "bar",
        data: {
          labels: etiquetes.map(function (e) { return e + " SMI"; }),
          datasets: [{ label: "% d'assalariats (" + t.anyo + ")",
                       data: etiquetes.map(function (e) { return 100 * t.tramos[e] / total; }),
                       backgroundColor: ROIG }],
        },
        options: fusiona({ indexAxis: "y",
          scales: { x: { ticks: { color: GRIS, callback: function (v) { return v + "%"; } } },
                    y: { ticks: { color: NEGRE, autoSkip: false, font: { size: 10 } } } } }),
      });
      taulaAccessible(cv.closest("figure"), ["Tram", "Assalariats", "%"],
        etiquetes.map(function (e) {
          return [e + " SMI", FMT0.format(t.tramos[e]), FMT.format(100 * t.tramos[e] / total)];
        }));
    });

    // 5b. Esforç per col·lectius
    grafic("grafColectius", function (cv) {
      var ec = ind.esfuerzo_colectivos;
      var files = [];
      ["De 18 a 25 años", "De 26 a 35 años"].forEach(function (k) {
        if (ec.edad[k]) files.push([k.replace("años", "anys").replace("De ", ""), ec.edad[k]]);
      });
      Object.keys(ec.sexo).forEach(function (k) {
        files.push([k === "Varón" ? "Homes" : "Dones", ec.sexo[k]]);
      });
      files.push(["Pensionistes", ec.pensionistas.total]);
      Object.keys(ec.sectores).forEach(function (k) {
        files.push([k.length > 32 ? k.slice(0, 30) + "…" : k, ec.sectores[k]]);
      });
      files.sort(function (a, b) { return b[1].tasa_alquiler_mediano_pct - a[1].tasa_alquiler_mediano_pct; });
      new Chart(cv, {
        type: "bar",
        data: {
          labels: files.map(function (f) { return f[0]; }),
          datasets: [{
            label: "% del net que costa el lloguer mitjà (" + ec.anyo + ")",
            data: files.map(function (f) { return f[1].tasa_alquiler_mediano_pct; }),
            backgroundColor: files.map(function (f) {
              return f[1].tasa_alquiler_mediano_pct >= 30 ? ROIG : NEGRE;
            }),
          }],
        },
        options: fusiona({ indexAxis: "y",
          scales: { x: { ticks: { color: GRIS, callback: function (v) { return v + "%"; } } },
                    y: { ticks: { color: NEGRE, autoSkip: false, font: { size: 10 } } } } }),
      });
      taulaAccessible(cv.closest("figure"),
        ["Col·lectiu", "Ingrés brut anual €", "Net mensual estimat €", "Taxa %"],
        files.map(function (f) {
          return [f[0], FMT0.format(f[1].bruto_anual),
                  FMT0.format(f[1].neto_mes_estimado), f[1].tasa_alquiler_mediano_pct];
        }));
    });

    // 6. Anys de salari per a comprar
    grafic("grafCompra", function (cv) {
      var s = ind.anyos_para_comprar.serie;
      var anys = anysOrdenats(s);
      new Chart(cv, {
        type: "line",
        data: { labels: anys,
          datasets: [{ label: "Anys de salari brut per a 90 m²",
                       data: anys.map(function (a) { return s[a]; }),
                       borderColor: ROIG, backgroundColor: ROIG, borderWidth: 3, pointRadius: 2 }] },
        options: fusiona(),
      });
      taulaAccessible(cv.closest("figure"), ["Any", "Anys de salari"],
        anys.map(function (a) { return [a, s[a]]; }));
    });

    // 7. Hipoteques anuals
    grafic("grafHipoteques", function (cv) {
      var h = dades.hipotecas.anual;
      var anys = anysOrdenats(h);
      new Chart(cv, {
        type: "bar",
        data: { labels: anys,
          datasets: [{ label: "Hipoteques sobre vivendes (província)",
                       data: anys.map(function (a) { return h[a].numero; }),
                       backgroundColor: NEGRE }] },
        options: fusiona(),
      });
      taulaAccessible(cv.closest("figure"), ["Any", "Hipoteques", "Import mitjà €"],
        anys.map(function (a) { return [a, FMT0.format(h[a].numero), FMT0.format(h[a].importe_medio_eur)]; }));
    });

    // 8. Desnonaments per causa
    grafic("grafDesnonaments", function (cv) {
      var d = ind.desahucios.anual_por_causa;
      var anys = anysOrdenats(d);
      var capes = [["lau", "Per impagament de lloguer (LAU)", ROIG],
                   ["ejecucion_hipotecaria", "Per execució hipotecària", NEGRE],
                   ["otros", "Altres", GRIS]];
      new Chart(cv, {
        type: "bar",
        data: { labels: anys,
          datasets: capes.map(function (c) {
            return { label: c[1], data: anys.map(function (a) { return d[a][c[0]]; }),
                     backgroundColor: c[2] };
          }) },
        options: fusiona({ scales: { x: { stacked: true, ticks: { color: GRIS }, grid: { display: false } },
                                     y: { stacked: true, ticks: { color: GRIS }, grid: { color: "#eee" } } } }),
      });
      taulaAccessible(cv.closest("figure"), ["Any", "Lloguer (LAU)", "Exec. hipotecària", "Altres", "Total"],
        anys.map(function (a) {
          return [a, d[a].lau, d[a].ejecucion_hipotecaria, d[a].otros, d[a].total];
        }));
    });

    // 9. Vivenda turística
    grafic("grafVT", function (cv) {
      var vt = ind.vivienda_turistica.castello;
      var ine = vt.estimacion_ine;
      var periodes = anysOrdenats(ine).filter(function (p) { return ine[p].vt != null; });
      var altes = vt.registro_gva.altas_acumuladas;
      var anysGva = anysOrdenats(altes).filter(function (a) { return a >= "2015"; });
      new Chart(cv, {
        type: "line",
        data: {
          labels: periodes,
          datasets: [{ label: "VT estimades per l'INE (plataformes)",
                       data: periodes.map(function (p) { return ine[p].vt; }),
                       borderColor: ROIG, backgroundColor: ROIG, borderWidth: 3, pointRadius: 3 }],
        },
        options: fusiona(),
      });
      var fig = cv.closest("figure");
      taulaAccessible(fig, ["Període", "VT estimades (INE)", "% del parc"],
        periodes.map(function (p) { return [p, ine[p].vt, ine[p].pct_parque]; }));
      var det = fig.querySelector("details.taula");
      if (det) {
        var html = "<p>Registre oficial GVA (altes acumulades de les VT hui inscrites):</p><table><thead><tr><th>Any</th><th>VT acumulades</th></tr></thead><tbody>";
        anysGva.forEach(function (a) { html += "<tr><th scope='row'>" + a + "</th><td>" + altes[a] + "</td></tr>"; });
        det.insertAdjacentHTML("beforeend", html + "</tbody></table>");
      }
    });

    // 10. Fiances (contractes de lloguer/any)
    grafic("grafFiances", function (cv) {
      var f = ind.fianzas.anual;
      var anys = anysOrdenats(f).filter(function (a) { return !f[a].parcial; });
      new Chart(cv, {
        type: "bar",
        data: { labels: anys,
          datasets: [{ label: "Fiances dipositades (contractes nous) a Castelló ciutat",
                       data: anys.map(function (a) { return f[a].municipio.fianzas; }),
                       backgroundColor: ROIG }] },
        options: fusiona(),
      });
      taulaAccessible(cv.closest("figure"), ["Any", "Contractes (ciutat)", "Import mitjà fiança €", "Contractes (província)"],
        anys.map(function (a) {
          return [a, f[a].municipio.fianzas, f[a].municipio.importe_medio_eur,
                  f[a].provincia.fianzas];
        }));
    });
  }

  // ---------- compartibles: PNG dels gràfics i cites amb font ----------
  function iniciaCompartibles() {
    document.querySelectorAll("figure.grafic").forEach(function (fig) {
      var canvas = fig.querySelector("canvas");
      var cap = fig.querySelector("figcaption");
      if (!canvas || !cap) return;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "descarrega";
      b.textContent = "⤓ PNG";
      b.setAttribute("aria-label", "Descarrega este gràfic com a imatge PNG");
      b.addEventListener("click", function () {
        if (pendents[canvas.id]) {          // encara no s'ha dibuixat
          pendents[canvas.id]();
          delete pendents[canvas.id];
        }
        setTimeout(function () {
          var chart = Chart.getChart(canvas);
          if (!chart) return;
          var a = document.createElement("a");
          a.href = chart.toBase64Image("image/png", 1);
          a.download = "observatori-castello-" + canvas.id + ".png";
          a.click();
        }, 150);
      });
      cap.appendChild(document.createTextNode(" "));
      cap.appendChild(b);
    });

    var url = location.href.split("#")[0];
    document.querySelectorAll("#dades-clau ul li").forEach(function (li) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "descarrega";
      b.textContent = "Copia la cita";
      b.addEventListener("click", function () {
        var text = li.textContent.replace("Copia la cita", "").trim() +
          " — Observatori de l'Habitatge de Castelló (CGT): " + url;
        navigator.clipboard.writeText(text).then(function () {
          b.textContent = "Copiada ✓";
          setTimeout(function () { b.textContent = "Copia la cita"; }, 2000);
        });
      });
      li.appendChild(document.createTextNode(" "));
      li.appendChild(b);
    });
  }

  // ---------- xifres del hero i dades clau ----------
  function iniciaXifres(dades) {
    var ind = dades.indicadores;
    var te = ind.tasa_esfuerzo.serie;
    var ultTe = anysOrdenats(te).pop();
    var i100 = ind.indice100.series.alquiler_m2;
    var ultI100 = anysOrdenats(i100).pop();
    var d = ind.desahucios;

    function posa(id, valor) {
      var el = document.getElementById(id);
      if (el) el.textContent = valor;
    }
    posa("xifraEsforc", FMT.format(te[ultTe].tasa_pct).replace(".", ",") + "%");
    posa("xifraEsforcAny", "dada " + ultTe);
    posa("xifraLloguer", "+" + FMT.format(i100[ultI100] - 100) + "%");
    posa("xifraLloguerAny", "2015–" + ultI100);
    posa("xifraDesnonaments", FMT0.format(d.acumulado.total));
    posa("xifraDesnonamentsAny", "2013–" + d.acumulado.hasta);
    posa("xifraLau", d.resumen.pct_lau + "%");
    posa("xifraLauAny", "dada " + d.resumen.anyo);
    // data d'actualització
    var gen = dades.meta.generado.slice(0, 10).split("-").reverse().join("/");
    posa("dataActualitzacio", gen);
  }

  // ---------- calculadores (3, una per pregunta) ----------
  var $ = function (id) { return document.getElementById(id); };

  function num(el) { return parseFloat(el.value) || 0; }

  function coma(v, dec) {
    return (dec === 0 ? FMT0 : FMT).format(v).replace(".", ",");
  }

  function escolta(camps, calcula) {
    camps.forEach(function (el) {
      ["input", "change"].forEach(function (ev) {
        el.addEventListener(ev, calcula);
      });
    });
    calcula();
  }

  // 1. "Quant se't menja el lloguer?": salari + lloguer
  function calcLloguer() {
    var C = window.CONFIG;
    var salari = $("inpSalari"), rang = $("inpSalariRang"),
        lloguer = $("inpLloguer");
    var ultimResultat = "";

    function calcula() {
      if (rang.value !== salari.value) rang.value = salari.value;
      var s = num(salari), l = num(lloguer);
      if (s <= 0 || l <= 0) return;

      var taxa = 100 * l / s;
      var dies = 30 * l / s;
      var res = $("resEsforc");
      res.querySelector("strong").textContent = coma(taxa) + "%";
      res.classList.remove("ok", "alerta", "perill");
      res.classList.add(taxa < 30 ? "ok" : taxa < 40 ? "alerta" : "perill");
      $("resEsforcNota").textContent =
        (taxa >= C.TAXA_MITJANA_PCT ? "per damunt" : "per davall") +
        " de la mitjana local (" + coma(C.TAXA_MITJANA_PCT) + "% el " +
        C.ANY_LLOGUER + ")";

      $("resDies").querySelector("strong").textContent = coma(dies);

      $("resIrav").querySelector("strong").textContent =
        "+" + coma(l * C.IRAV.pct / 100) + " €/mes";
      $("resIravNota").textContent =
        "és el màxim legal que et poden pujar el lloguer enguany (IRAV " +
        C.IRAV.etiqueta + ": " + coma(C.IRAV.pct) +
        "%), si el contracte és posterior al 25/05/2023";

      ultimResultat = "Treballe " + coma(dies) +
        " dies al mes només per a pagar l'habitatge (el " + coma(taxa) +
        "% del meu sou). I tu? Calcula-ho a l'Observatori de l'Habitatge " +
        "de Castelló:";
    }

    rang.addEventListener("input", function () {
      salari.value = rang.value; calcula();
    });
    escolta([salari, lloguer], calcula);

    $("btnCompartir").addEventListener("click", function () {
      calcula();
      if (!ultimResultat) return;
      var url = location.href.split("#")[0];
      if (navigator.share) {
        navigator.share({ text: ultimResultat, url: url }).catch(function () {});
      } else {
        navigator.clipboard.writeText(ultimResultat + " " + url).then(function () {
          $("btnCompartir").textContent = "Copiat al porta-retalls ✓";
          setTimeout(function () {
            $("btnCompartir").textContent = "Compartix el teu resultat";
          }, 2500);
        });
      }
    });
  }

  // 2. "Quant hauries de cobrar?": salari + any de referència
  function calcInflacio() {
    var C = window.CONFIG;
    var salari = $("inpSalariInf"), anyRef = $("inpAnyInf");

    Object.keys(C.IPC_ANUAL).sort().forEach(function (a) {
      var op = document.createElement("option");
      op.value = a; op.textContent = a;
      if (a === "2020") op.selected = true;
      anyRef.appendChild(op);
    });

    function calcula() {
      var s = num(salari);
      if (s <= 0) return;
      var any = anyRef.value;
      var factor = C.IPC_ULTIM.valor / C.IPC_ANUAL[any];
      var equivalent = s * factor;
      $("resPoder").querySelector("strong").textContent =
        FMT0.format(equivalent) + " €";
      $("resPoderNota").textContent =
        "hauries de cobrar hui per a comprar el mateix que amb " +
        FMT0.format(s) + " € l'any " + any + " (inflació provincial +" +
        coma(100 * (factor - 1)) + "% fins a " + C.IPC_ULTIM.etiqueta + ")";
      $("resPerdua").querySelector("strong").textContent =
        "−" + FMT0.format(equivalent - s) + " €/mes";
      $("resPerduaNota").textContent =
        "de poder adquisitiu estàs perdent cada mes si cobres igual que l'any " +
        any;
    }

    escolta([salari, anyRef], calcula);
  }

  // 3. "I si vullgueres comprar?": només el salari
  function calcCompra() {
    var C = window.CONFIG;
    var salari = $("inpSalariCompra");

    function calcula() {
      var s = num(salari);
      if (s <= 0) return;
      var preu = C.PREU_M2_TAXAT * C.SUPERFICIE_TIPUS_M2;
      $("resComprar").querySelector("strong").textContent =
        coma(preu / (s * 12)) + " anys";
      $("resComprarNota").textContent =
        "de salari íntegre per a una vivenda de " + C.SUPERFICIE_TIPUS_M2 +
        " m² (" + FMT0.format(preu) + " €, valor taxat " + C.ANY_PREU + ")";
      var entrada = preu * C.ENTRADA_PCT;
      $("resEntrada").querySelector("strong").textContent =
        coma(entrada / (s * 12 * C.ESTALVI_PCT)) + " anys";
      $("resEntradaNota").textContent =
        "estalviant el " + Math.round(C.ESTALVI_PCT * 100) +
        "% del teu sou per a l'entrada i les despeses de compra (" +
        FMT0.format(entrada) + " €)";
    }

    escolta([salari], calcula);
  }

  function iniciaCalculadora() {
    calcLloguer();
    calcInflacio();
    calcCompra();
  }

  // ---------- metodologia ----------
  function iniciaMetodologia(dades) {
    var cos = document.getElementById("taulaFonts");
    if (!cos) return;
    var meta = dades.meta.fuentes;
    Object.keys(meta).forEach(function (k) {
      var f = meta[k];
      var tr = document.createElement("tr");
      tr.innerHTML = "<td>" + f.nombre + "</td><td>" + f.ultimo_dato +
        "</td><td>" + f.fecha_descarga + "</td>";
      cos.appendChild(tr);
    });
  }

  // ---------- arranc ----------
  document.addEventListener("DOMContentLoaded", function () {
    carregaTot().then(function (dades) {
      iniciaXifres(dades);
      iniciaGrafics(dades);
      iniciaMetodologia(dades);
      iniciaCompartibles();
    }).catch(function (err) {
      console.error("Error carregant dades:", err);
      var avis = document.getElementById("avisError");
      if (avis) avis.hidden = false;
    });
    iniciaCalculadora();
  });
})();
