/* Mapa de seccions censals de Castelló ciutat: renda (ADRH) i lloguer
   (SERPAVI), dues capes commutables. Sense tesel·les externes (cap crida a
   tercers): coropletes sobre fons neutre. S'inicialitza en fer-se visible. */

(function () {
  "use strict";

  var iniciat = false;

  function carrega(nom) {
    return fetch("data/" + nom, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(nom + ": HTTP " + r.status);
      return r.json();
    });
  }

  function dadesInline(clau) {
    return window.OBSERVATORI_DADES && window.OBSERVATORI_DADES[clau];
  }

  function quantils(valors, n) {
    var v = valors.slice().sort(function (a, b) { return a - b; });
    var talls = [];
    for (var i = 1; i < n; i++) {
      talls.push(v[Math.floor(v.length * i / n)]);
    }
    return talls;
  }

  function classe(valor, talls) {
    for (var i = 0; i < talls.length; i++) {
      if (valor < talls[i]) return i;
    }
    return talls.length;
  }

  var FMT0 = new Intl.NumberFormat("ca-ES", { maximumFractionDigits: 0 });
  var FMT2 = new Intl.NumberFormat("ca-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function ultimAny(seccions, camp) {
    var anys = {};
    Object.keys(seccions).forEach(function (s) {
      Object.keys(seccions[s]).forEach(function (a) {
        if (seccions[s][a] && seccions[s][a][camp] != null) anys[a] = true;
      });
    });
    return Object.keys(anys).sort().pop();
  }

  function inicia() {
    if (iniciat) return;
    iniciat = true;

    Promise.all([
      dadesInline("secciones_geojson") || carrega("secciones.geojson"),
      dadesInline("mapa_renta") || carrega("mapa_renta.json"),
      dadesInline("mapa_alquiler") || carrega("mapa_alquiler.json"),
    ]).then(function (res) {
      var geo = res[0], renta = res[1].secciones, lloguer = res[2].secciones;

      var anyRenda = ultimAny(renta, "renta_neta_persona");
      var anyLloguer = ultimAny(lloguer, "eur_m2");

      // definició de les dues capes
      var CAPES = {
        renda: {
          titol: "Renda neta per persona (" + anyRenda + ")",
          valor: function (cusec) {
            var s = renta[cusec];
            return s && s[anyRenda] ? s[anyRenda].renta_neta_persona : null;
          },
          format: function (v) { return FMT0.format(v) + " €/any"; },
          colors: ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"],
          font: "INE, Atles de Distribució de Renda de les Llars",
        },
        lloguer: {
          titol: "Lloguer mitjà (" + anyLloguer + ")",
          valor: function (cusec) {
            var s = lloguer[cusec];
            return s && s[anyLloguer] ? s[anyLloguer].eur_m2 : null;
          },
          format: function (v) { return FMT2.format(v) + " €/m²/mes"; },
          colors: ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"],
          font: "SERPAVI (MIVAU), contractes reals",
        },
      };

      Object.keys(CAPES).forEach(function (k) {
        var c = CAPES[k];
        var valors = [];
        geo.features.forEach(function (f) {
          var v = c.valor(f.properties.CUSEC);
          if (v != null) valors.push(v);
        });
        c.talls = quantils(valors, c.colors.length);
      });

      var mapa = L.map("elMapa", {
        attributionControl: true,
        scrollWheelZoom: false,
        zoomSnap: 0.25,
      });
      mapa.attributionControl.setPrefix(false);
      mapa.attributionControl.addAttribution(
        "Seccionat censal © INE · Dades: SERPAVI (MIVAU) i ADRH (INE)");
      document.getElementById("elMapa").style.background = "#dfe8ee";

      var capaActual = "renda";
      var capaGeo;
      var limits = L.geoJSON(geo).getBounds();
      var mogutPerLusuari = false;

      // Enquadra la ciutat dins del marc. Es torna a cridar quan canvia la
      // mida del contenidor: si el mapa es crea abans que el navegador haja
      // acabat la maquetació, Leaflet es queda amb una mida antiga i el
      // dibuix ix xicotet i descentrat.
      function enquadra() {
        mapa.invalidateSize({ animate: false });
        mapa.fitBounds(limits, { padding: [12, 12], animate: false });
      }

      function pinta(nomCapa) {
        capaActual = nomCapa;
        var c = CAPES[nomCapa];
        if (capaGeo) mapa.removeLayer(capaGeo);
        capaGeo = L.geoJSON(geo, {
          style: function (f) {
            var v = c.valor(f.properties.CUSEC);
            return {
              weight: 1, color: "#ffffff", fillOpacity: v == null ? 0.15 : 0.85,
              fillColor: v == null ? "#999" : c.colors[classe(v, c.talls)],
            };
          },
          onEachFeature: function (f, capa) {
            var cusec = f.properties.CUSEC;
            var v = c.valor(cusec);
            var etiqueta = "Secció " + cusec.slice(5, 7) + "-" + cusec.slice(7);
            capa.bindTooltip("<strong>" + etiqueta + "</strong><br>" +
              c.titol + ": " + (v == null ? "sense dada" : c.format(v)),
              { sticky: true });
          },
        }).addTo(mapa);
        if (!mogutPerLusuari) enquadra();
        // llegenda
        var leg = document.getElementById("llegendaMapa");
        var html = "<strong>" + c.titol + "</strong> · font: " + c.font + "<br>";
        var previ = null;
        for (var i = 0; i < c.colors.length; i++) {
          var fins = i < c.talls.length ? c.talls[i] : null;
          html += '<span class="clau" style="background:' + c.colors[i] + '"></span>';
          if (previ == null) html += "&lt; " + c.format(fins);
          else if (fins == null) html += "&ge; " + c.format(previ);
          else html += c.format(previ) + " – " + c.format(fins);
          html += "&nbsp;&nbsp;";
          previ = fins;
        }
        leg.innerHTML = html;
        // estat dels botons
        document.querySelectorAll("#mapa .commutador button").forEach(function (b) {
          var actiu = b.dataset.capa === nomCapa;
          b.classList.toggle("actiu", actiu);
          b.setAttribute("aria-pressed", actiu ? "true" : "false");
        });
      }

      document.querySelectorAll("#mapa .commutador button").forEach(function (b) {
        b.addEventListener("click", function () { pinta(b.dataset.capa); });
      });

      pinta(capaActual);

      // l'usuari mana: si mou o fa zoom, ja no reenquadrem
      mapa.on("dragstart zoomstart", function () { mogutPerLusuari = true; });

      var contenidorMapa = document.getElementById("elMapa");
      if (window.ResizeObserver) {
        new ResizeObserver(function () {
          if (!mogutPerLusuari) enquadra();
        }).observe(contenidorMapa);
      } else {
        window.addEventListener("resize", function () {
          if (!mogutPerLusuari) enquadra();
        });
      }
      // després de les fonts web i de qualsevol reflux inicial
      setTimeout(function () { if (!mogutPerLusuari) enquadra(); }, 300);
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(function () {
          if (!mogutPerLusuari) enquadra();
        });
      }
    }).catch(function (err) {
      console.error("Error carregant el mapa:", err);
      var el = document.getElementById("elMapa");
      if (el) el.textContent = "No s'ha pogut carregar el mapa.";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var contenidor = document.getElementById("elMapa");
    if (!contenidor || typeof L === "undefined") return;
    new IntersectionObserver(function (entrades, obs) {
      entrades.forEach(function (e) {
        if (e.isIntersecting) { inicia(); obs.disconnect(); }
      });
    }, { rootMargin: "200px" }).observe(contenidor);
  });
})();
