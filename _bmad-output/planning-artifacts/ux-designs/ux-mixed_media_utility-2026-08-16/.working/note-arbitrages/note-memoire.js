/* ================= MEMOIRE DURABLE DE LA PAGE =================
   La page se republie elle-meme : les reponses et les notes vivent dans
   son HTML, se relisent depuis une session Claude, et ne dependent pas
   d'un export manuel. Le stockage du navigateur reste le filet.

   Ce module s'execute AVANT la couche de commentaires : il capture le
   balisage d'origine avant que la couche n'y injecte ses pastilles, et
   c'est ce balisage-la qui est republie. */
window.__memoire = (function () {
  var SNAP = document.getElementById("page").innerHTML;   // avant toute injection
  var CLE_SCROLL = "mmu-arb7-scroll";
  var etatInitial = { notes: null, choix: {} };
  try {
    var brut = document.getElementById("etat");
    if (brut) {
      var d = JSON.parse(brut.textContent || "{}");
      if (d && typeof d === "object") {
        etatInitial.notes = d.notes && Object.keys(d.notes).length ? d.notes : null;
        etatInitial.choix = d.choix || {};
      }
    }
  } catch (e) {}

  var api = null, verifie = false;
  var notes = etatInitial.notes || {};
  var choix = {};
  Object.keys(etatInitial.choix).forEach(function (k) { choix[k] = etatInitial.choix[k]; });

  var attente = false, minuteur = null, enCours = false;

  function etatEl() { return document.getElementById("memoire-etat"); }
  function dire(txt, cls) {
    var e = etatEl(); if (!e) return;
    e.textContent = txt; e.className = cls || "";
  }

  function serialiser() {
    function bloc(id, tag) {
      var e = document.getElementById(id);
      return e ? "<" + tag + ' id="' + id + '">\n' + e.textContent + "\n</" + tag + ">" : "";
    }
    var json = JSON.stringify({ notes: notes, choix: choix }).replace(/</g, "\\u003c");
    return '<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
      + '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">\n'
      + "<title>Arbitrages de l'Epic 7</title>\n"
      + bloc("css-page", "style") + "\n" + bloc("css-couche", "style") + "\n"
      + '</head>\n<body>\n<div id="page">' + SNAP + "</div>\n"
      + '<script type="application/json" id="etat">' + json + "<\/script>\n"
      + bloc("js-memoire", "script") + "\n"
      + bloc("js-couche", "script") + "\n"
      + bloc("js-choix", "script") + "\n"
      + "</body>\n</html>";
  }

  // On ne republie jamais pendant que le lecteur ecrit : la republication
  // recharge la vue, et rechargerait sous ses doigts. On attend qu'aucune
  // feuille ne soit ouverte et qu'aucun champ n'ait le focus.
  function occupe() {
    if (document.querySelector(".c-sheet.open")) return true;
    var a = document.activeElement;
    return !!(a && (a.tagName === "TEXTAREA" || a.tagName === "INPUT"));
  }

  function tenter() {
    if (!attente || enCours) return;
    if (occupe()) return;
    attente = false;
    enCours = true;
    dire("Enregistrement dans la page…", "");
    try { sessionStorage.setItem(CLE_SCROLL, String(window.scrollY)); } catch (e) {}
    api.publish(serialiser()).then(function () {
      enCours = false;
      dire("Tes réponses sont enregistrées dans la page.", "ok");
    })["catch"](function (err) {
      enCours = false;
      var code = err && err.code ? err.code : "upstream_error";
      if (code === "conflict") { dire("La page a changé ailleurs : elle se recharge.", ""); return; }
      dire("Enregistrement dans la page impossible (" + code + "). Ce que tu écris reste sur cet appareil : termine par « Exporter ».", "bad");
    });
  }

  function publier() {
    if (!api) return false;
    attente = true;
    if (minuteur) clearTimeout(minuteur);
    minuteur = setTimeout(tenter, 1200);
    return true;
  }

  setInterval(function () { if (attente) tenter(); }, 1500);

  if (window.claude && window.claude.use) {
    window.claude.use("artifact").then(function (ns) {
      api = ns; verifie = true;
      if (api) dire("Tes réponses s'enregistrent dans la page : je les relis d'ici.", "ok");
      else dire("Enregistrement dans la page indisponible sur cette vue. Ce que tu écris reste sur cet appareil : termine par « Exporter » et envoie-le-moi.", "bad");
    })["catch"](function () {
      verifie = true;
      dire("Enregistrement dans la page indisponible sur cette vue. Termine par « Exporter ».", "bad");
    });
  } else {
    verifie = true;
    dire("Enregistrement dans la page indisponible sur cette vue. Termine par « Exporter ».", "bad");
  }

  try {
    var y = sessionStorage.getItem(CLE_SCROLL);
    if (y) { sessionStorage.removeItem(CLE_SCROLL); window.addEventListener("load", function () { window.scrollTo(0, parseInt(y, 10) || 0); }); }
  } catch (e) {}

  return {
    notesInitiales: function () { return etatInitial.notes; },
    choixInitiaux: function () { return etatInitial.choix; },
    choix: function () { return choix; },
    majNotes: function (n) { notes = n; return publier(); },
    majChoix: function (point, val) { choix[point] = val; return publier(); },
    disponible: function () { return !!api; }
  };
})();
