/* Recherche partout : Ctrl+K (ou ⌘K, ou « chercher » sur le meuble) ouvre une fenêtre qui cherche dans toutes les notes
   de tous les meubles ; ↑ ↓ pour choisir, Entrée pour ouvrir la note sur son mur, Échap pour fermer. */
(function () {
  'use strict';
  var hub = window.ndsHub;
  if (!hub) return;
  var root = null, input = null, list = null, results = [], pick = 0, timer = 0;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function snippet(body, q) {
    var line = String(body || '').split('\n').find(function (ln) { return ln.toLowerCase().indexOf(q) >= 0; }) || '';
    return line.replace(/^\s*[-*]\s\[[ xX]\]\s?/, '').slice(0, 90);
  }
  function build() {
    root = el('div', 'k-root'); root.hidden = true;
    root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'true'); root.setAttribute('aria-label', T('Chercher partout'));
    var back = el('div', 'k-back'); back.addEventListener('click', close);
    var panel = el('div', 'k-panel');
    input = el('input', 'k-in'); input.type = 'search'; input.placeholder = T('Chercher dans tous les meubles…');
    input.setAttribute('aria-label', T('Chercher dans tous les meubles…'));
    list = el('div', 'k-list'); list.setAttribute('role', 'listbox');
    panel.appendChild(input); panel.appendChild(list);
    root.appendChild(back); root.appendChild(panel);
    document.body.appendChild(root);
    input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 80); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); choose(pick); }
      else if (e.key === 'Escape') { e.preventDefault(); close(); }
      e.stopPropagation();
    });
  }
  function run() {
    var q = input.value.trim().toLowerCase();
    results = hub.search(q); pick = 0;
    list.textContent = '';
    if (q && !results.length) list.appendChild(el('div', 'k-empty', T('Aucun résultat')));
    results.forEach(function (r, i) {
      var b = el('button', 'k-row'); b.type = 'button'; b.setAttribute('role', 'option');
      var dot = el('i', 'sdot s-' + r.status);
      var mid = el('span', 'k-mid');
      mid.appendChild(el('span', 'k-t', (r.ask ? '❓ ' : '') + r.title));
      var sn = snippet(r.body, q);
      mid.appendChild(el('span', 'k-p', r.path + (sn ? ' · ' + sn : '')));
      b.appendChild(dot); b.appendChild(mid);
      b.addEventListener('click', function () { choose(i); });
      b.addEventListener('mousemove', function () { if (pick !== i) { pick = i; mark(); } });
      list.appendChild(b);
    });
    mark();
  }
  function mark() {
    Array.from(list.querySelectorAll('.k-row')).forEach(function (b, i) {
      b.classList.toggle('on', i === pick); b.setAttribute('aria-selected', i === pick ? 'true' : 'false');
      if (i === pick) b.scrollIntoView({ block: 'nearest' });
    });
  }
  function move(d) { if (results.length) { pick = (pick + d + results.length) % results.length; mark(); } }
  function choose(i) { var r = results[i]; if (!r) return; close(); hub.openNote(r.id); }
  function open() {
    if (!root) build();
    root.hidden = false; input.value = ''; list.textContent = ''; results = [];
    requestAnimationFrame(function () { root.classList.add('show'); input.focus(); });
  }
  function close() {
    if (!root || root.hidden) return;
    root.classList.remove('show'); root.hidden = true;
  }
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); open(); }
  });
  var link = document.getElementById('cSearch');
  if (link) link.addEventListener('click', open);
  window.ndsSearch = { open: open };
})();
