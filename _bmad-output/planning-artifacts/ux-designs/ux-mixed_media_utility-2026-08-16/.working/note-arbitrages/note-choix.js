/* ================= REPONDRE PAR UNE TOUCHE =================
   Une option touchee vaut une reponse : elle se marque, se garde dans la
   page, et part dans le bloc exporte avec les notes. */
(function () {
  var initiaux = window.__memoire ? window.__memoire.choixInitiaux() : {};

  function peindre(bloc) {
    var point = bloc.getAttribute("data-point");
    var val = bloc.getAttribute("data-choisi") || "";
    Array.prototype.forEach.call(bloc.querySelectorAll(".opt"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-val") === val ? "true" : "false");
    });
    var etat = bloc.querySelector(".choix-etat");
    if (etat) {
      etat.textContent = val ? "Ta réponse : " + point + val : "Pas encore répondu";
      etat.className = "choix-etat" + (val ? " repondu" : "");
    }
  }

  // La reprise par collage rappelle ce repeintre : les reponses rechargees
  // doivent se voir, pas seulement etre en memoire.
  window.__repeindreChoix = function () {
    var c = window.__memoire ? window.__memoire.choix() : {};
    Array.prototype.forEach.call(document.querySelectorAll(".choix"), function (bloc) {
      var v = c[bloc.getAttribute("data-point")];
      if (v) bloc.setAttribute("data-choisi", v); else bloc.removeAttribute("data-choisi");
      peindre(bloc);
    });
  };

  Array.prototype.forEach.call(document.querySelectorAll(".choix"), function (bloc) {
    var point = bloc.getAttribute("data-point");
    if (initiaux[point]) bloc.setAttribute("data-choisi", initiaux[point]);
    peindre(bloc);
    Array.prototype.forEach.call(bloc.querySelectorAll(".opt"), function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        var val = b.getAttribute("data-val");
        // retoucher l'option deja choisie la retire : on peut se raviser
        if (bloc.getAttribute("data-choisi") === val) bloc.removeAttribute("data-choisi");
        else bloc.setAttribute("data-choisi", val);
        peindre(bloc);
        if (window.__memoire) window.__memoire.majChoix(point, bloc.getAttribute("data-choisi") || "");
      });
    });
  });
})();
