(function () {
  'use strict';

  // =========================================================================
  // 1. Enregistrement des retours
  //    La page se republie elle-meme : les retours vivent dans son HTML, donc
  //    ils survivent a la fermeture de l'onglet et se relisent depuis la
  //    session Claude. Filet local (localStorage) au cas ou la republication
  //    echoue : rien de ce qui est ecrit ne doit pouvoir se perdre.
  // =========================================================================

  var LS_NOTES = 'mmu-planche-notes';
  var LS_DRAFTS = 'mmu-planche-brouillons';
  var SS_SCROLL = 'mmu-planche-scroll';
  var api = null;          // namespace artifact, ou null
  var apiChecked = false;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text != null) { e.textContent = text; }
    return e;
  }

  function stamp() {
    var d = new Date();
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return p(d.getDate()) + '/' + p(d.getMonth() + 1) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  // Un retour = un bloc autonome : la date dans son element, le texte dans le
  // sien (jamais de texte mele a des elements), et le bouton de suppression.
  function makeNote(text, when) {
    var note = el('p', 'note');
    var body = el('span', 'body');
    body.appendChild(el('span', 'when', when || stamp()));
    body.appendChild(document.createTextNode(text));
    var del = el('button', 'del', '×');
    del.type = 'button';
    del.setAttribute('aria-label', 'Supprimer ce retour');
    note.appendChild(body);
    note.appendChild(del);
    return note;
  }

  function collect() {
    var out = {};
    Array.prototype.forEach.call(document.querySelectorAll('.note-block'), function (b) {
      var list = [];
      Array.prototype.forEach.call(b.querySelectorAll('.note'), function (n) {
        var when = n.querySelector('.when');
        var body = n.querySelector('.body');
        var txt = body ? body.textContent.slice(when ? when.textContent.length : 0) : '';
        list.push({ when: when ? when.textContent : '', text: txt });
      });
      if (list.length) { out[b.getAttribute('data-key')] = list; }
    });
    return out;
  }

  function backup() {
    try { localStorage.setItem(LS_NOTES, JSON.stringify(collect())); } catch (e) {}
  }

  // Le document republie est reconstruit a partir d'un clone nettoye : l'etat
  // transitoire (visionneuse ouverte, messages de statut) ne doit pas se figer
  // dans la page que le prochain lecteur recevra.
  function serialize() {
    var clone = document.getElementById('app').cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll('.status'), function (s) {
      s.textContent = ''; s.className = 'status';
    });
    var v = clone.querySelector('#viewer');
    if (v) { v.hidden = true; }
    var vi = clone.querySelector('#viewer-img');
    if (vi) { vi.removeAttribute('src'); vi.removeAttribute('style'); vi.alt = ''; }
    var m = clone.querySelector('#mode');
    if (m) { m.textContent = 'Verification de l’enregistrement…'; m.className = 'mode'; }
    return '<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
      + '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">\n'
      + '<title>Planche de contact</title>\n'
      + '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
      + '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
      + '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@400;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@500&display=swap">\n'
      + '<style id="css">\n' + document.getElementById('css').textContent + '\n</style>\n'
      + '</head>\n<body>\n<div id="app">' + clone.innerHTML + '</div>\n'
      + '<script id="app-js">\n' + document.getElementById('app-js').textContent + '\n<\/script>\n'
      + '</body>\n</html>';
  }

  function saveDrafts() {
    var d = {};
    Array.prototype.forEach.call(document.querySelectorAll('.note-block'), function (b) {
      var ta = b.querySelector('.note-input');
      if (ta && ta.value.trim()) { d[b.getAttribute('data-key')] = ta.value; }
    });
    try { sessionStorage.setItem(LS_DRAFTS, JSON.stringify(d)); } catch (e) {}
  }

  function restoreDrafts() {
    var d;
    try { d = JSON.parse(sessionStorage.getItem(LS_DRAFTS) || '{}'); } catch (e) { return; }
    Object.keys(d).forEach(function (k) {
      var b = document.querySelector('.note-block[data-key="' + k + '"]');
      if (b) { b.querySelector('.note-input').value = d[k]; }
    });
  }

  function say(status, msg, kind) {
    if (!status) { return; }
    status.textContent = msg;
    status.className = 'status' + (kind ? ' ' + kind : '');
  }

  var ERRORS = {
    not_writer: 'Cette vue est en lecture seule : le retour est garde sur cet appareil, envoie-le en conversation.',
    not_granted: 'Enregistrement indisponible ici : le retour est garde sur cet appareil, envoie-le en conversation.',
    not_declared: 'Enregistrement indisponible ici : le retour est garde sur cet appareil, envoie-le en conversation.',
    capability_disabled: 'Enregistrement indisponible ici : le retour est garde sur cet appareil, envoie-le en conversation.',
    rate_limited: 'Trop d’enregistrements rapproches. Attends quelques secondes et reappuie.',
    too_large: 'La page a atteint sa taille limite. Envoie ce retour en conversation.',
    conflict: 'La page a change entre-temps, elle se recharge : verifie que le retour est bien la.'
  };

  // La republication recharge la vue : on met de cote la position de lecture
  // et les brouillons non enregistres avant de partir.
  function persist(status) {
    backup();
    if (!api) {
      say(status, 'Garde sur cet appareil seulement — utilise « Copier tous mes retours ».', 'warn');
      return;
    }
    say(status, 'Enregistrement…');
    saveDrafts();
    try { sessionStorage.setItem(SS_SCROLL, String(window.scrollY)); } catch (e) {}
    api.publish(serialize()).then(function () {
      say(status, 'Enregistre.', 'done');
    })['catch'](function (err) {
      var code = err && err.code ? err.code : 'upstream_error';
      say(status, ERRORS[code] || 'Enregistrement impossible pour le moment. Le retour est garde sur cet appareil.', 'warn');
    });
  }

  document.addEventListener('click', function (e) {
    var save = e.target.closest ? e.target.closest('.save') : null;
    if (save) {
      var block = save.closest('.note-block');
      var ta = block.querySelector('.note-input');
      var status = block.querySelector('.status');
      var text = ta.value.trim();
      if (!text) { say(status, 'Rien a enregistrer.', 'warn'); ta.focus(); return; }
      block.querySelector('.notes').appendChild(makeNote(text));
      ta.value = '';
      persist(status);
      return;
    }
    var del = e.target.closest ? e.target.closest('.note .del') : null;
    if (del) {
      var blk = del.closest('.note-block');
      del.closest('.note').remove();
      persist(blk.querySelector('.status'));
    }
  });

  // Copier : dernier recours si l'enregistrement ne passe pas, et raccourci
  // pour envoyer les retours en conversation.
  var copyBtn = document.getElementById('copy-all');
  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      var st = document.getElementById('copy-status');
      var lines = [];
      Array.prototype.forEach.call(document.querySelectorAll('.note-block'), function (b) {
        var notes = b.querySelectorAll('.note');
        if (!notes.length) { return; }
        lines.push('## ' + b.getAttribute('data-key'));
        Array.prototype.forEach.call(notes, function (n) {
          var when = n.querySelector('.when');
          var body = n.querySelector('.body');
          lines.push('- ' + (when ? '(' + when.textContent + ') ' : '')
            + body.textContent.slice(when ? when.textContent.length : 0));
        });
        lines.push('');
      });
      if (!lines.length) { say(st, 'Aucun retour a copier.', 'warn'); return; }
      var txt = lines.join('\n');
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(function () {
          say(st, 'Copie. Colle-les dans la conversation.', 'done');
        })['catch'](function () { say(st, 'Copie refusee par le navigateur.', 'warn'); });
      } else {
        say(st, 'Copie indisponible dans ce navigateur.', 'warn');
      }
    });
  }

  // =========================================================================
  // 2. Visionneuse plein ecran
  // =========================================================================

  var viewer = document.getElementById('viewer');
  var scroll = document.getElementById('viewer-scroll');
  var vimg = document.getElementById('viewer-img');
  var vtitle = document.getElementById('viewer-title');
  var btnIn = document.getElementById('zoom-in');
  var btnOut = document.getElementById('zoom-out');
  var btnFit = document.getElementById('zoom-fit');
  var btnClose = document.getElementById('viewer-close');
  var opener = null;
  var fitWidth = 0;
  var scale = 1;

  function apply(next, anchor) {
    var prevW = vimg.clientWidth || fitWidth;
    var prevH = vimg.clientHeight || 1;
    var ax = anchor ? anchor.x : (scroll.scrollLeft + scroll.clientWidth / 2) / Math.max(prevW, 1);
    var ay = anchor ? anchor.y : (scroll.scrollTop + scroll.clientHeight / 2) / Math.max(prevH, 1);
    scale = Math.min(4, Math.max(1, next));
    vimg.style.width = (fitWidth * scale) + 'px';
    scroll.scrollLeft = ax * vimg.clientWidth - scroll.clientWidth / 2;
    scroll.scrollTop = ay * vimg.clientHeight - scroll.clientHeight / 2;
    btnOut.disabled = scale <= 1;
    btnIn.disabled = scale >= 4;
  }

  function fit() {
    fitWidth = scroll.clientWidth;
    apply(1);
    scroll.scrollLeft = 0;
    scroll.scrollTop = 0;
  }

  function openViewer(src, label, alt) {
    opener = document.activeElement;
    vimg.src = src;
    vimg.alt = alt || '';
    vtitle.textContent = label || '';
    viewer.hidden = false;
    document.body.classList.add('locked');
    if (vimg.complete) { fit(); } else { vimg.onload = fit; }
    btnClose.focus();
  }

  function closeViewer() {
    viewer.hidden = true;
    document.body.classList.remove('locked');
    vimg.removeAttribute('src');
    vimg.removeAttribute('style');
    if (opener && opener.focus) { opener.focus(); }
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.shot') : null;
    if (!b) { return; }
    var inner = b.querySelector('img');
    openViewer(b.getAttribute('data-img'), b.getAttribute('data-title'), inner ? inner.alt : '');
  });

  btnIn.addEventListener('click', function () { apply(scale * 1.6); });
  btnOut.addEventListener('click', function () { apply(scale / 1.6); });
  btnFit.addEventListener('click', fit);
  btnClose.addEventListener('click', closeViewer);

  var lastTap = 0;
  scroll.addEventListener('click', function (e) {
    if (e.target !== vimg) { return; }
    var now = Date.now();
    if (now - lastTap < 350) {
      var r = vimg.getBoundingClientRect();
      apply(scale > 1.05 ? 1 : 2.5, { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height });
    }
    lastTap = now;
  });

  document.addEventListener('keydown', function (e) {
    if (viewer.hidden) { return; }
    if (e.key === 'Escape') { closeViewer(); }
    if (e.key === '+' || e.key === '=') { apply(scale * 1.6); }
    if (e.key === '-') { apply(scale / 1.6); }
  });

  window.addEventListener('resize', function () { if (!viewer.hidden) { fit(); } });

  // =========================================================================
  // 3. Reprise apres rechargement, puis annonce du mode d'enregistrement
  // =========================================================================

  restoreDrafts();
  try {
    var y = sessionStorage.getItem(SS_SCROLL);
    if (y) { sessionStorage.removeItem(SS_SCROLL); window.scrollTo(0, parseInt(y, 10) || 0); }
  } catch (e) {}

  var mode = document.getElementById('mode');
  function announce() {
    if (!mode) { return; }
    if (api) {
      mode.textContent = 'Tes retours s’enregistrent dans la page : je les relis d’ici.';
      mode.className = 'mode';
    } else {
      mode.textContent = 'Enregistrement dans la page indisponible sur cette vue. Ce que tu ecris reste sur cet appareil : termine par « Copier tous mes retours » et colle-les dans la conversation.';
      mode.className = 'mode warn';
    }
  }
  if (window.claude && window.claude.use) {
    window.claude.use('artifact').then(function (ns) { api = ns; apiChecked = true; announce(); })
      ['catch'](function () { apiChecked = true; announce(); });
  } else {
    apiChecked = true;
    announce();
  }
})();
