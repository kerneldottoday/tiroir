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
  function cabinets() { return window.ndsMeubles ? window.ndsMeubles.list() : []; }
  function scopeText(inv) {
    if (inv.cabinets && inv.cabinets.length) {
      var cn = {}; cabinets().forEach(function (c) { cn[c.id] = c.name; });
      return T('meuble « {name} »', { name: inv.cabinets.map(function (id) { return cn[id] || '?'; }).join(', ') });
    }
    if (!inv.folders) return T('tout le Tiroir');
    var names = {};
    hub.allTabs().forEach(function (g) { g.tabs.forEach(function (f) { names[f.id] = g.name + ' / ' + f.name; }); });
    var list = inv.folders.map(function (id) { return names[id]; }).filter(Boolean);
    return list.length ? list.join(', ') : T('aucun dossier (supprimés)');
  }
  function say(msg, bad) { var m = root.querySelector('.sh-msg'); m.textContent = msg; m.classList.toggle('bad', !!bad); }

  function copy(text, btn) {
    var done = function () { var t = btn.textContent; btn.textContent = T('Copié ✓'); setTimeout(function () { btn.textContent = t; }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { window.prompt(T('Copie ce lien :'), text); });
    } else window.prompt(T('Copie ce lien :'), text);
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
    /* à quoi la personne a accès : tout, un meuble (avec ses futurs tiroirs), ou des intercalaires choisis */
    form.appendChild(el('span', 'lab', T('Accès à')));
    var scope = el('div', 'sh-scopes');
    [['all', T('tout le Tiroir')], ['cabinet', T('un meuble')], ['tabs', T('des intercalaires')]].forEach(function (r, i) {
      var l = el('label', 'sh-check'); var inp = el('input'); inp.type = 'radio'; inp.name = 'shScope'; inp.value = r[0]; inp.checked = i === 0;
      inp.addEventListener('change', showScope);
      l.appendChild(inp); l.appendChild(el('span', '', r[1])); scope.appendChild(l);
    });
    form.appendChild(scope);
    var cab = el('select', 'sh-in sh-cab'); cab.id = 'shCab'; cab.setAttribute('aria-label', T('un meuble'));
    form.appendChild(cab);
    form.appendChild(el('p', 'sh-hint sh-cab-hint', T('Les tiroirs que tu ajouteras plus tard à ce meuble seront visibles aussi.')));
    var box = el('div', 'sh-folders'); form.appendChild(box);
    var go = el('button', 'btn primary', T('Créer le lien')); go.type = 'submit'; form.appendChild(go);
    form.appendChild(el('p', 'sh-msg'));
    form.addEventListener('submit', function (e) { e.preventDefault(); create(name, box); });
    panel.appendChild(form);
    panel.appendChild(el('div', 'lab sh-sub', T('Liens actifs')));
    panel.appendChild(el('div', 'sh-list'));
    root.appendChild(panel);
  }
  function scopeKind() { return (root.querySelector('input[name=shScope]:checked') || {}).value || 'all'; }
  function showScope() {
    var k = scopeKind();
    root.querySelector('.sh-cab').hidden = k !== 'cabinet';
    root.querySelector('.sh-cab-hint').hidden = k !== 'cabinet';
    root.querySelector('.sh-folders').hidden = k !== 'tabs';
  }
  function fillFolders() {
    var cab = root.querySelector('.sh-cab'); cab.textContent = '';
    var cur = window.ndsMeubles ? window.ndsMeubles.current() : '';
    cabinets().forEach(function (c) { var o = el('option', '', c.name); o.value = c.id; o.selected = c.id === cur; cab.appendChild(o); });
    root.querySelector('input[name=shScope][value=cabinet]').disabled = !cabinets().length;
    var box = root.querySelector('.sh-folders'); box.textContent = '';
    hub.allTabs().forEach(function (g) {
      var grp = el('div', 'sh-group');
      grp.appendChild(el('div', 'sh-gname', g.name));
      g.tabs.forEach(function (f) {
        var l = el('label', 'sh-check'); var c = el('input'); c.type = 'checkbox'; c.value = f.id;
        l.appendChild(c); l.appendChild(el('span', '', f.name)); grp.appendChild(l);
      });
      box.appendChild(grp);
    });
    showScope();
  }
  function renderList() {
    var list = root.querySelector('.sh-list'); list.textContent = '';
    if (!invites.length) { list.appendChild(el('p', 'sh-empty', T('Aucun lien pour l’instant.'))); return; }
    invites.slice().sort(function (a, b) { return (b.createdAt || 0) - (a.createdAt || 0); }).forEach(function (inv) {
      var row = el('div', 'sh-row');
      var info = el('div', 'sh-info');
      var top = el('div', 'sh-who'); top.appendChild(el('b', '', inv.label));
      top.appendChild(el('span', 'sh-pill' + (inv.role === 'edit' ? ' edit' : ''), inv.role === 'edit' ? T('édition') : T('lecture')));
      info.appendChild(top); info.appendChild(el('div', 'sh-scope', scopeText(inv)));
      var acts = el('div', 'sh-acts');
      var cp = el('button', 'btn', T('Copier le lien')); cp.type = 'button';
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
      .catch(function () { say(T('Impossible de charger les liens.'), true); });
  }
  function create(name, box) {
    var label = name.value.replace(/\s+/g, ' ').trim();
    if (!label) { say(T('Donne un nom à ce lien.'), true); name.focus(); return; }
    var kind = scopeKind();
    var picked = Array.from(box.querySelectorAll('input:checked')).map(function (c) { return c.value; });
    if (kind === 'tabs' && !picked.length) { say(T('Choisis au moins un intercalaire.'), true); return; }
    var cab = root.querySelector('.sh-cab').value;
    var role = (root.querySelector('input[name=shRole]:checked') || {}).value || 'view';
    var id = 'i' + Date.now().toString(36) + Math.floor(Math.random() * 1296).toString(36);
    var body = { label: label, role: role, folders: kind === 'tabs' ? picked : null, cabinets: kind === 'cabinet' && cab ? [cab] : null };
    api('PUT', '/api/invites/' + id, body).then(function (inv) {
      invites.push(inv); renderList(); name.value = '';
      var first = root.querySelector('.sh-row .btn');
      if (first) copy(linkOf(inv), first);
      say(T('Lien créé et copié : envoie-le à {name}.', { name: inv.label }));
    }).catch(function (e) { say(T('Erreur : {m}', { m: e.message }), true); });
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
    }).catch(function (e) { say(T('Erreur : {m}', { m: e.message }), true); });
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
