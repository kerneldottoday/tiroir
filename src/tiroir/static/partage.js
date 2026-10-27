/* Partage (admin) : liens d'invitation en lecture ou en édition, pour tous les dossiers ou une sélection.
   Le serveur impose les droits ; ce panneau ne fait que les créer, les copier et les révoquer. */
(function () {
  'use strict';
  var hub = window.ndsHub;
  var root = document.getElementById('share');
  if (!hub || !root) return;
  var invites = [], built = false, lastFocus = null;

  function api(method, path, body) {
    return fetch(path, { method: method, credentials: 'same-origin', headers: { 'X-Tiroir': '1', 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body) }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok) throw new Error(j.error || ('http ' + r.status)); return j; });
    });
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function linkOf(inv) { return location.origin + '/i/' + inv.token; }
  function scopeText(inv) {
    if (!inv.folders) return T('tous les dossiers');
    var names = {}; hub.folders().forEach(function (f) { names[f.id] = f.name; });
    var list = inv.folders.map(function (id) { return names[id]; }).filter(Boolean);
    return list.length ? list.join(', ') : T('aucun dossier (supprimés)');
  }
  function say(msg, bad) { var m = root.querySelector('.sh-msg'); m.textContent = msg; m.classList.toggle('bad', !!bad); }

  function copy(text, btn) {
    var done = function () { var t = btn.textContent; btn.textContent = T('Copié ✓'); setTimeout(function () { btn.textContent = t; }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { window.prompt('Copie ce lien :', text); });
    } else window.prompt('Copie ce lien :', text);
  }

  /* ---------- construction du panneau ---------- */
  function build() {
    if (built) return;
    built = true;
    root.appendChild(el('div', 'sh-back')).addEventListener('click', close);
    var panel = el('div', 'sh-panel');
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true'); panel.setAttribute('aria-labelledby', 'shTitle');
    var head = el('div', 'sh-head');
    var h = el('h2', '', T('Partager le Tiroir')); h.id = 'shTitle';
    var x = el('button', 'h-link', T('fermer')); x.type = 'button'; x.addEventListener('click', close);
    head.appendChild(h); head.appendChild(x); panel.appendChild(head);
    panel.appendChild(el('p', 'sh-note', T('Un lien ouvre le Tiroir sans mot de passe. Lecture = consulter ; édition = créer et modifier des post-it. Seul toi peux supprimer.')));

    var form = el('form', 'sh-form'); form.autocomplete = 'off';
    var lab = el('label', 'lab', T('Nom de la personne')); lab.htmlFor = 'shName';
    var name = el('input', 'sh-in'); name.id = 'shName'; name.maxLength = 40; name.placeholder = T('ex. Alex');
    form.appendChild(lab); form.appendChild(name);
    form.appendChild(el('span', 'lab', T('Accès')));
    var seg = el('div', 'sh-seg');
    [['view', T('Lecture')], ['edit', T('Édition')]].forEach(function (r, i) {
      var l = el('label', 'sh-opt'); var inp = el('input'); inp.type = 'radio'; inp.name = 'shRole'; inp.value = r[0]; inp.checked = i === 0;
      l.appendChild(inp); l.appendChild(el('span', '', r[1])); seg.appendChild(l);
    });
    form.appendChild(seg);
    form.appendChild(el('span', 'lab', T('Dossiers')));
    var all = el('label', 'sh-check'); var allIn = el('input'); allIn.type = 'checkbox'; allIn.checked = true; allIn.id = 'shAll';
    all.appendChild(allIn); all.appendChild(el('span', '', T('Tous (y compris les futurs)')));
    form.appendChild(all);
    var box = el('div', 'sh-folders'); form.appendChild(box);
    allIn.addEventListener('change', function () { box.classList.toggle('off', allIn.checked); });
    var go = el('button', 'btn primary', T('Créer le lien')); go.type = 'submit'; form.appendChild(go);
    form.appendChild(el('p', 'sh-msg'));
    form.addEventListener('submit', function (e) { e.preventDefault(); create(name, allIn, box); });
    panel.appendChild(form);
    panel.appendChild(el('div', 'lab sh-sub', T('Liens actifs')));
    panel.appendChild(el('div', 'sh-list'));
    root.appendChild(panel);
  }
  function fillFolders() {
    var box = root.querySelector('.sh-folders'); box.textContent = '';
    box.classList.toggle('off', root.querySelector('#shAll').checked);
    hub.folders().forEach(function (f) {
      var l = el('label', 'sh-check'); var c = el('input'); c.type = 'checkbox'; c.value = f.id;
      l.appendChild(c); l.appendChild(el('span', '', f.name)); box.appendChild(l);
    });
  }
  function renderList() {
    var list = root.querySelector('.sh-list'); list.textContent = '';
    if (!invites.length) { list.appendChild(el('p', 'sh-empty', 'Aucun lien pour l’instant.')); return; }
    invites.slice().sort(function (a, b) { return (b.createdAt || 0) - (a.createdAt || 0); }).forEach(function (inv) {
      var row = el('div', 'sh-row');
      var info = el('div', 'sh-info');
      var top = el('div', 'sh-who'); top.appendChild(el('b', '', inv.label));
      top.appendChild(el('span', 'sh-pill' + (inv.role === 'edit' ? ' edit' : ''), inv.role === 'edit' ? T('édition') : T('lecture')));
      info.appendChild(top); info.appendChild(el('div', 'sh-scope', scopeText(inv)));
      var acts = el('div', 'sh-acts');
      var cp = el('button', 'btn', 'Copier le lien'); cp.type = 'button';
      cp.addEventListener('click', function () { copy(linkOf(inv), cp); });
      var del = el('button', 'btn danger', T('Révoquer')); del.type = 'button';
      del.addEventListener('click', function () { revoke(inv, del); });
      acts.appendChild(cp); acts.appendChild(del);
      row.appendChild(info); row.appendChild(acts); list.appendChild(row);
    });
  }

  /* ---------- actions ---------- */
  function load() {
    api('GET', '/api/invites').then(function (j) { invites = j.invites || []; renderList(); })
      .catch(function () { say('Impossible de charger les liens.', true); });
  }
  function create(name, allIn, box) {
    var label = name.value.replace(/\s+/g, ' ').trim();
    if (!label) { say('Donne un nom à ce lien.', true); name.focus(); return; }
    var picked = Array.from(box.querySelectorAll('input:checked')).map(function (c) { return c.value; });
    if (!allIn.checked && !picked.length) { say('Choisis au moins un dossier.', true); return; }
    var role = (root.querySelector('input[name=shRole]:checked') || {}).value || 'view';
    var id = 'i' + Date.now().toString(36) + Math.floor(Math.random() * 1296).toString(36);
    api('PUT', '/api/invites/' + id, { label: label, role: role, folders: allIn.checked ? null : picked }).then(function (inv) {
      invites.push(inv); renderList(); name.value = '';
      var first = root.querySelector('.sh-row .btn');
      if (first) copy(linkOf(inv), first);
      say(T('Lien créé et copié : envoie-le à {name}.', { name: inv.label }));
    }).catch(function (e) { say('Erreur : ' + e.message, true); });
  }
  function revoke(inv, btn) {
    if (!btn.classList.contains('armed')) {
      btn.classList.add('armed'); btn.textContent = T('Sûr ?');
      setTimeout(function () { btn.classList.remove('armed'); btn.textContent = T('Révoquer'); }, 3000);
      return;
    }
    api('DELETE', '/api/invites/' + inv.id).then(function () {
      invites = invites.filter(function (x) { return x.id !== inv.id; });
      renderList(); say(T('Lien révoqué : {name} n’a plus accès.', { name: inv.label }));
    }).catch(function (e) { say('Erreur : ' + e.message, true); });
  }

  function open() {
    if (hub.role() !== 'admin') return;
    lastFocus = document.activeElement;
    build(); fillFolders(); say('');
    root.hidden = false;
    load();
    root.querySelector('#shName').focus();
  }
  function close() {
    root.hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !root.hidden) { e.stopPropagation(); close(); } }, true);
  window.ndsShare = { open: open };
})();
