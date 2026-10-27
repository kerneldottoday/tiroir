/* Texte d'une note sur le mur : lignes « - [ ] » = cases à cocher (cliquables sur la carte), adresses http(s) = liens.
   Tout est construit avec des nœuds DOM (jamais innerHTML) : le texte d'une note, y compris celui d'un agent, reste du texte.
   Dans la fiche, « + case » ajoute une ligne à cocher. */
(function () {
  'use strict';
  var CHECK = /^(\s*[-*]\s\[)( |x|X)(\]\s?)(.*)$/;
  var URL = /https?:\/\/[^\s<>"'`]+/g;

  function linkify(parent, text) {
    var last = 0, m;
    URL.lastIndex = 0;
    while ((m = URL.exec(text))) {
      var url = m[0].replace(/[.,;:!?)\]]+$/, '');
      if (m.index > last) parent.appendChild(document.createTextNode(text.slice(last, m.index)));
      var a = document.createElement('a');
      a.href = url; a.textContent = url.replace(/^https?:\/\//, '');
      a.target = '_blank'; a.rel = 'noopener noreferrer nofollow';
      parent.appendChild(a);
      last = m.index + url.length;
    }
    if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
  }

  /* « fait / total » des cases d'un texte (0, 0 s'il n'y en a pas) */
  function progress(text) {
    var done = 0, total = 0;
    String(text || '').split('\n').forEach(function (ln) {
      var m = CHECK.exec(ln);
      if (m) { total++; if (m[2] !== ' ') done++; }
    });
    return [done, total];
  }

  /* remplit `box` avec le texte ; onChange(nouveauTexte) quand une case est cochée (null = lecture seule) */
  function body(box, text, onChange) {
    box.textContent = '';
    var lines = String(text || '').split('\n');
    lines.forEach(function (ln, i) {
      var m = CHECK.exec(ln);
      var row = document.createElement('div');
      if (!m) {
        row.className = 'nl';
        linkify(row, ln || ' ');
        box.appendChild(row);
        return;
      }
      row.className = 'ck' + (m[2] !== ' ' ? ' done' : '');
      var cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = m[2] !== ' '; cb.disabled = !onChange;
      cb.setAttribute('aria-label', m[4] || '');
      cb.addEventListener('change', function () {
        var next = lines.slice();
        next[i] = m[1] + (cb.checked ? 'x' : ' ') + m[3] + m[4];
        onChange(next.join('\n'));
      });
      var span = document.createElement('span');
      linkify(span, m[4]);
      row.appendChild(cb); row.appendChild(span);
      box.appendChild(row);
    });
  }

  /* un clic sur une case ou un lien ne doit pas saisir la carte pour la déplacer */
  document.addEventListener('pointerdown', function (e) {
    if (e.target.closest && e.target.closest('.note .nb input, .note .nb a')) e.stopPropagation();
  }, true);

  /* fiche : « + case » insère une ligne à cocher là où est le curseur */
  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('fCheck'), ta = document.getElementById('fBody');
    if (!btn || !ta) return;
    btn.addEventListener('click', function () {
      if (ta.disabled) return;
      var at = ta.selectionStart || ta.value.length, before = ta.value.slice(0, at);
      var add = (before && !before.endsWith('\n') ? '\n' : '') + '- [ ] ';
      ta.value = before + add + ta.value.slice(at);
      ta.focus();
      ta.selectionStart = ta.selectionEnd = at + add.length;
      ta.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });

  window.ndsText = { body: body, progress: progress };
})();
