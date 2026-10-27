(function () {
  'use strict';
  var STATUS = {
    todo:  { label: T('À faire'),  order: 0 },
    doing: { label: T('En cours'), order: 1 },
    info:  { label: T('Info'),     order: 2 },
    done:  { label: T('Fait'),     order: 3 }
  };
  var NOTE_W = 232, NOTE_H = 150, MINK = 0.15, MAXK = 2.5;
  var $ = function (id) { return document.getElementById(id); };
  var app = $('app'), board = $('board'), world = $('world'), rowsEl = $('rows'), chipsEl = $('chips'), mini = $('mini');

  var notes = new Map(), els = new Map(), folders = new Map(), projects = new Map();
  var curProject = ''; /* tiroir ouvert (projet) : ses intercalaires sont les dossiers dont folder.project === curProject */
  var cur = 'all', editingF = null; /* cur : 'all' (tous), 'none' (sans dossier), 'trash' (corbeille) ou id d'un dossier */
  var me = { role: 'view', folders: null, label: '' }; /* droits de la session (GET /api/me) ; le serveur les impose de toute façon */
  function isAdmin() { return me.role === 'admin'; }
  function canWrite() { return me.role === 'admin' || me.role === 'edit'; }
  var sel = null, filter = 'all', query = '';
  var view = { x: 40, y: 40, k: 1 };
  var col = null, readOnly = false, online = false, savedView = false, fitted = false, maxZ = 1;
  var patches = new Map(), timers = new Map(), queues = new Map();
  var anim = 0;

  /* ---------- utilitaires ---------- */
  function hash(s) { var h = 0; for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return Math.abs(h); }
  function num(v, d) { return typeof v === 'number' && isFinite(v) ? v : d; }
  function str(v, d) { return typeof v === 'string' ? v : d; }
  function pad(n) { return String(n || 0).padStart(3, '0'); }
  function clamp(v, a, b) { return Math.min(b, Math.max(a, v)); }
  function fmtDate(t) { try { return new Date(t).toLocaleString(window.tiroirLang === 'en' ? 'en-GB' : 'fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }); } catch (e) { return ''; } }
  function clean(id, d) {
    var st = STATUS[d.status] ? d.status : 'info';
    return { id: id, title: str(d.title, ''), body: str(d.body, ''), status: st, tag: str(d.tag, ''),
             x: num(d.x, 0), y: num(d.y, 0), z: num(d.z, 1), n: num(d.n, 0), createdAt: num(d.createdAt, 0), updatedAt: num(d.updatedAt, 0), src: str(d.src, ''),
             folder: str(d.folder, ''), deletedAt: num(d.deletedAt, 0), trashedWith: str(d.trashedWith, '') };
  }
  function liveFolder(fid) { var f = folders.get(fid); return !!f && !f.deletedAt; }
  function folderOf(n) { return liveFolder(n.folder) ? n.folder : ''; }
  function visible(n) {
    if (cur === 'trash') return !!n.deletedAt;
    if (n.deletedAt) return false;
    return cur === 'all' || (cur === 'none' ? !folderOf(n) : n.folder === cur);
  }
  function visibleNotes() { return Array.from(notes.values()).filter(visible); }
  function folderName(id) { var f = folders.get(id); return f ? f.name : ''; }
  function curLabel() {
    if (cur === 'all') return T('Tous les projets');
    if (cur === 'none') return T('Sans dossier');
    if (cur === 'trash') return T('Corbeille');
    var p = projects.get((folders.get(cur) || {}).project);
    return (p ? p.name + ' / ' : '') + folderName(cur);
  }

  /* ---------- données (ton serveur : /api/notes, protégé par mot de passe) ---------- */
  var inited = false, busy = 0, loading = false;
  function setSync() {
    var s = $('sync'), t = $('syncTxt');
    s.className = online ? 'on' : '';
    t.textContent = online ? T('En ligne') : (inited ? T('Hors ligne') : T('Connexion'));
  }
  function api(method, path, body) {
    return fetch(path, { method: method, credentials: 'same-origin',
      headers: { 'X-Tiroir': '1', 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body) }).then(function (r) {
      if (r.status === 401) { location.href = '/'; throw new Error('auth'); }
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json();
    });
  }
  function enqueue(id, fn) {
    busy++;
    var p = (queues.get(id) || Promise.resolve()).then(fn).then(function () { online = true; setSync(); })
      .catch(function () { online = false; setSync(); })
      .then(function () { busy--; });
    queues.set(id, p);
    return p;
  }
  function persist(id, patch) {
    var n = notes.get(id);
    if (!n) return;
    if (patch.title !== undefined || patch.body !== undefined || patch.status !== undefined || patch.tag !== undefined) patch.updatedAt = Date.now();
    Object.keys(patch).forEach(function (k) { n[k] = patch[k]; });
    updateCard(id); renderList(); drawMini();
    enqueue(id, function () { return api('PATCH', '/api/notes/' + id, patch); });
  }
  function queuePatch(id, patch) {
    var cur = patches.get(id) || {};
    Object.keys(patch).forEach(function (k) { cur[k] = patch[k]; });
    patches.set(id, cur);
    var n = notes.get(id);
    if (n) { Object.keys(patch).forEach(function (k) { n[k] = patch[k]; }); updateCard(id); renderList(); }
    clearTimeout(timers.get(id));
    timers.set(id, setTimeout(function () { flush(id); }, 600));
  }
  function flush(id) {
    clearTimeout(timers.get(id)); timers.delete(id);
    var p = patches.get(id); if (!p) return;
    patches.delete(id); persist(id, p);
  }
  function createNote(x, y) {
    if (!canWrite() || cur === 'trash') return;
    var n = 0; notes.forEach(function (v) { n = Math.max(n, v.n); });
    var id = 'n' + Date.now().toString(36) + Math.floor(Math.random() * 1296).toString(36);
    var now = Date.now();
    var note = { id: id, title: T('Nouvelle note'), body: '', status: 'todo', tag: '', src: '', x: Math.round(x), y: Math.round(y), z: ++maxZ, n: n + 1, createdAt: now, updatedAt: now,
                 folder: liveFolder(cur) ? cur : (me.folders ? ((sortedFolders()[0] || {}).id || '') : '') };
    notes.set(id, note);
    enqueue(id, function () { var d = Object.assign({}, note); delete d.id; return api('PUT', '/api/notes/' + id, d); });
    renderAll(); select(id, false);
    $('fTitle').focus(); $('fTitle').select();
  }
  /* supprimer = corbeille (30 jours) avec « Annuler » ; depuis la corbeille = effacement définitif. Admin seulement. */
  function deleteNote(id) {
    var n = notes.get(id);
    if (!n || !isAdmin()) return;
    flush(id);
    var purge = !!n.deletedAt;
    if (purge) notes.delete(id); else n.deletedAt = Date.now();
    if (sel === id) sel = null;
    renderAll(); syncSel();
    enqueue(id, function () { return api('DELETE', '/api/notes/' + id + (purge ? '?purge=1' : '')); });
    if (purge) toast('Note effacée définitivement');
    else toast('Note mise à la corbeille', T('Annuler'), function () { restoreNote(id); });
  }
  function restoreNote(id) {
    var n = notes.get(id);
    if (!n || !isAdmin()) return;
    n.deletedAt = 0;
    if (sel === id && !visible(n)) sel = null;
    renderAll(); syncSel();
    enqueue(id, function () { return api('PATCH', '/api/notes/' + id, { restore: true }); });
  }
  var toastT = 0;
  function toast(msg, action, fn) {
    var el = $('toast'); el.textContent = '';
    var s = document.createElement('span'); s.textContent = msg; el.appendChild(s);
    if (action) {
      var b = document.createElement('button'); b.type = 'button'; b.textContent = action;
      b.addEventListener('click', function () { fn(); el.classList.remove('show'); });
      el.appendChild(b);
    }
    el.classList.add('show');
    clearTimeout(toastT); toastT = setTimeout(function () { el.classList.remove('show'); }, 6000);
  }
  function onNotes(list, flist, plist) {
    if (busy > 0 || patches.size > 0) return;
    if (editingF === null) {
      folders = new Map();
      flist.forEach(function (f) {
        if (f && typeof f.id === 'string') folders.set(f.id, { id: f.id, name: str(f.name, '?'), order: num(f.order, 0),
                                                              archived: f.archived === true, deletedAt: num(f.deletedAt, 0),
                                                              project: str(f.project, ''), trashedWith: str(f.trashedWith, '') });
      });
      projects = new Map();
      plist.forEach(function (p) {
        if (p && typeof p.id === 'string') projects.set(p.id, { id: p.id, name: str(p.name, '?'), order: num(p.order, 0), archived: p.archived === true,
                                                                deletedAt: num(p.deletedAt, 0) });
      });
      if (mode() === 'wall' && cur !== 'all' && cur !== 'none' && cur !== 'trash' && !liveFolder(cur)) goHome();
    }
    var seen = new Set();
    list.forEach(function (d) {
      if (!d || typeof d.id !== 'string') return;
      seen.add(d.id);
      if (dragId === d.id) return;
      notes.set(d.id, clean(d.id, d));
    });
    Array.from(notes.keys()).forEach(function (id) { if (!seen.has(id)) notes.delete(id); });
    online = true; maxZ = 1; notes.forEach(function (v) { maxZ = Math.max(maxZ, v.z); });
    if (sel && (!notes.has(sel) || !visible(notes.get(sel)))) sel = null;
    renderAll(); syncSel(true);
    if (!fitted && notes.size) { fitted = true; if (!savedView) fitAll(false); }
    renderFolders();
    setSync();
  }
  function load() {
    if (loading || dragId) return Promise.resolve();
    loading = true;
    return fetch('/api/notes', { credentials: 'same-origin' }).then(function (r) {
      if (r.status === 401) { location.href = '/'; throw new Error('auth'); }
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json();
    }).then(function (j) { onNotes(j.notes || [], j.folders || [], j.projects || []); })
      .catch(function () { online = false; setSync(); })
      .then(function () { loading = false; inited = true; setSync(); });
  }
  function loadMe() {
    return fetch('/api/me', { credentials: 'same-origin' }).then(function (r) {
      if (r.status === 401) { location.href = '/'; throw new Error('auth'); }
      return r.json();
    }).then(function (j) {
      me = { role: j.role === 'admin' || j.role === 'edit' ? j.role : 'view', folders: Array.isArray(j.folders) ? j.folders : null, label: str(j.label, '') };
    }).catch(function () {});
  }
  function applyRole() {
    readOnly = !canWrite();
    document.body.dataset.role = me.role;
    var b = $('roleBadge');
    b.hidden = isAdmin();
    b.textContent = me.role === 'edit' ? T('Invité · édition') : T('Invité · lecture');
  }
  function initApi() {
    load();
    setInterval(function () { if (!document.hidden) load(); }, 10000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) load(); });
  }

  /* ---------- rendu du mur ---------- */
  function cardEl(id) {
    var el = document.createElement('div');
    el.className = 'note'; el.dataset.id = id;
    el.innerHTML = '<div class="pin"></div><div class="nh"><span></span><i class="sdot"></i></div><div class="nt"></div><div class="nb"></div>';
    world.appendChild(el); els.set(id, el);
    return el;
  }
  function updateCard(id) {
    var n = notes.get(id); if (!n) return;
    if (!visible(n)) { var old = els.get(id); if (old) { old.remove(); els.delete(id); } return; }
    var el = els.get(id) || cardEl(id);
    el.style.left = n.x + 'px'; el.style.top = n.y + 'px'; el.style.zIndex = n.z;
    el.style.setProperty('--rot', (((hash(id) % 5) - 2) * 0.5) + 'deg');
    var fl = folderName(folderOf(n)) || n.tag;
    el.children[1].children[0].textContent = pad(n.n) + (fl ? ' · ' + fl : '');
    el.children[1].children[1].className = 'sdot s-' + n.status;
    el.children[2].textContent = n.title || T('Sans titre');
    el.children[3].textContent = n.body;
    el.children[3].style.display = n.body ? '' : 'none';
    el.classList.toggle('sel', sel === id);
  }
  function renderAll() {
    els.forEach(function (el, id) { if (!notes.has(id)) { el.remove(); els.delete(id); } });
    notes.forEach(function (_, id) { updateCard(id); });
    $('empty').classList.toggle('hide', els.size > 0);
    renderList(); drawMini(); updateCount(); renderFolders();
  }
  function updateCount() {
    var c = { todo: 0, doing: 0, done: 0, info: 0 }, vis = visibleNotes();
    vis.forEach(function (n) { c[n.status]++; });
    if (editingF === null) $('where').textContent = curLabel();
  }

  /* ---------- liste ---------- */
  function renderList() {
    var vis = visibleNotes();
    var counts = { all: vis.length, todo: 0, doing: 0, info: 0, done: 0 };
    vis.forEach(function (n) { counts[n.status]++; });
    chipsEl.textContent = '';
    ['all', 'todo', 'doing', 'info', 'done'].forEach(function (k) {
      var b = document.createElement('button'); b.type = 'button'; b.className = 'chip';
      b.setAttribute('aria-pressed', filter === k ? 'true' : 'false');
      b.textContent = (k === 'all' ? T('Tout') : STATUS[k].label) + ' ' + counts[k];
      b.addEventListener('click', function () { filter = k; renderList(); });
      chipsEl.appendChild(b);
    });
    var q = query.trim().toLowerCase();
    var arr = vis.filter(function (n) {
      if (filter !== 'all' && n.status !== filter) return false;
      return !q || (n.title + ' ' + n.body + ' ' + n.tag).toLowerCase().indexOf(q) >= 0;
    }).sort(function (a, b) { return STATUS[a.status].order - STATUS[b.status].order || b.updatedAt - a.updatedAt; });
    rowsEl.textContent = '';
    arr.forEach(function (n) {
      var b = document.createElement('button'); b.type = 'button'; b.className = 'row';
      b.setAttribute('aria-current', sel === n.id ? 'true' : 'false');
      var mk = document.createElement('span'); mk.className = 'mk'; mk.textContent = '▶';
      var mid = document.createElement('span');
      var t = document.createElement('span'); t.className = 'rt'; t.textContent = n.title || T('Sans titre');
      var fl = folderName(folderOf(n)) || n.tag;
      var s = document.createElement('span'); s.className = 'rs'; s.textContent = pad(n.n) + (fl ? ' · ' + fl : '') + ' · ' + STATUS[n.status].label;
      mid.appendChild(t); mid.appendChild(s);
      var d = document.createElement('span'); d.className = 'sdot s-' + n.status;
      b.appendChild(mk); b.appendChild(mid); b.appendChild(d);
      b.addEventListener('click', function () { select(n.id, true); $('list').classList.remove('open'); });
      rowsEl.appendChild(b);
    });
    if (!arr.length) { var e = document.createElement('div'); e.className = 'lab'; e.style.padding = '16px 8px'; e.textContent = vis.length ? T('Aucun résultat') : T('Rien pour l’instant'); rowsEl.appendChild(e); }
  }

  /* ---------- sélection et fiche ---------- */
  function select(id, focus) {
    if (sel && sel !== id) flush(sel);
    sel = id; syncSel(); renderList();
    var n = notes.get(id);
    if (n) { n.z = ++maxZ; persist(id, { z: n.z }); }
    if (focus) focusNote(id);
  }
  function deselect() { if (sel) flush(sel); sel = null; syncSel(); renderList(); }
  function syncSel(fromSnap) {
    els.forEach(function (el, id) { el.classList.toggle('sel', id === sel); });
    app.classList.toggle('has-sel', !!sel);
    var n = sel && notes.get(sel);
    if (!n) return;
    $('fid').textContent = pad(n.n);
    var editing = fromSnap && document.getElementById('fiche').contains(document.activeElement);
    if (!editing) { fillFolderSelect(folderOf(n)); $('fTitle').value = n.title; $('fBody').value = n.body; }
    $('fMeta').textContent = T('Modifiée le {d}', { d: fmtDate(n.updatedAt || n.createdAt) }) + (n.src ? ' · ' + T('Source : {s}', { s: n.src }) : '');
    Array.from($('seg').children).forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.s === n.status ? 'true' : 'false'); });
    var trash = !!n.deletedAt, ro = readOnly || trash;
    ['fTitle', 'fBody', 'fFolder'].forEach(function (i) { $(i).disabled = ro; });
    Array.from($('seg').children).forEach(function (b) { b.disabled = ro; });
    $('fRestore').hidden = !(trash && isAdmin());
    $('fCenter').hidden = trash;
    resetDel();
  }
  function buildSeg() {
    var seg = $('seg');
    Object.keys(STATUS).forEach(function (k) {
      var b = document.createElement('button'); b.type = 'button'; b.dataset.s = k;
      var d = document.createElement('i'); d.className = 'sdot s-' + k;
      var t = document.createElement('span'); t.textContent = STATUS[k].label;
      b.appendChild(d); b.appendChild(t);
      b.addEventListener('click', function () { var n = sel && notes.get(sel); if (n && !readOnly && !n.deletedAt) { persist(sel, { status: k }); syncSel(); } });
      seg.appendChild(b);
    });
  }
  var delTimer = 0;
  function resetDel() {
    clearTimeout(delTimer);
    var b = $('fDel'), n = sel && notes.get(sel);
    b.classList.remove('armed'); b.textContent = n && n.deletedAt ? T('Effacer définitivement') : T('Supprimer');
  }

  /* ---------- vue : zoom, déplacement ---------- */
  function applyView() {
    world.style.transform = 'translate(' + view.x + 'px,' + view.y + 'px) scale(' + view.k + ')';
    var g = 24 * view.k;
    board.style.backgroundSize = g + 'px ' + g + 'px';
    board.style.backgroundPosition = view.x + 'px ' + view.y + 'px';
    $('zLab').textContent = Math.round(view.k * 100) + '%';
    drawMini();
    clearTimeout(applyView.t);
    var key = 'tiroir-view:' + cur;
    applyView.t = setTimeout(function () { try { localStorage.setItem(key, JSON.stringify(view)); } catch (e) {} }, 400);
  }
  function zoomAt(cx, cy, f) {
    var r = board.getBoundingClientRect(), px = cx - r.left, py = cy - r.top;
    var k = clamp(view.k * f, MINK, MAXK);
    view.x = px - (px - view.x) * (k / view.k); view.y = py - (py - view.y) * (k / view.k); view.k = k;
    applyView();
  }
  function animateTo(t, ms) {
    cancelAnimationFrame(anim);
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !ms) { view = t; applyView(); return; }
    var s = { x: view.x, y: view.y, k: view.k }, t0 = performance.now();
    (function step(now) {
      var p = clamp((now - t0) / ms, 0, 1), e = 1 - Math.pow(1 - p, 3);
      view = { x: s.x + (t.x - s.x) * e, y: s.y + (t.y - s.y) * e, k: s.k + (t.k - s.k) * e };
      applyView();
      if (p < 1) anim = requestAnimationFrame(step);
    })(t0);
  }
  function focusNote(id) {
    var n = notes.get(id); if (!n) return;
    var r = board.getBoundingClientRect(), k = clamp(Math.max(view.k, 0.9), MINK, 1.4);
    animateTo({ x: r.width / 2 - (n.x + NOTE_W / 2) * k, y: r.height / 2 - (n.y + NOTE_H / 2) * k, k: k }, 320);
  }
  function bounds() {
    var vis = visibleNotes();
    if (!vis.length) return null;
    var a = 1e9, b = 1e9, c = -1e9, d = -1e9;
    vis.forEach(function (n) { a = Math.min(a, n.x); b = Math.min(b, n.y); c = Math.max(c, n.x + NOTE_W); d = Math.max(d, n.y + NOTE_H); });
    return { x0: a, y0: b, x1: c, y1: d };
  }
  function fitAll(anim_) {
    var bb = bounds(), r = board.getBoundingClientRect();
    if (!bb) { animateTo({ x: 40, y: 40, k: 1 }, anim_ === false ? 0 : 300); return; }
    var pad = 70, w = bb.x1 - bb.x0, h = bb.y1 - bb.y0;
    var k = clamp(Math.min((r.width - pad * 2) / w, (r.height - pad * 2) / h), MINK, 1.2);
    animateTo({ x: r.width / 2 - (bb.x0 + w / 2) * k, y: r.height / 2 - (bb.y0 + h / 2) * k, k: k }, anim_ === false ? 0 : 300);
  }
  function worldPoint(cx, cy) { var r = board.getBoundingClientRect(); return { x: (cx - r.left - view.x) / view.k, y: (cy - r.top - view.y) / view.k }; }

  /* ---------- gestes ---------- */
  var ptrs = new Map(), drag = null, pinch = null, dragId = null;
  board.addEventListener('pointerdown', function (e) {
    if (e.target.closest('.hint')) return;
    cancelAnimationFrame(anim);
    try { board.setPointerCapture(e.pointerId); } catch (x) {}
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (ptrs.size === 2) {
      var p = Array.from(ptrs.values());
      pinch = { d0: Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y) || 1, k0: view.k,
                mid: { x: (p[0].x + p[1].x) / 2, y: (p[0].y + p[1].y) / 2 }, w: null };
      pinch.w = worldPoint(pinch.mid.x, pinch.mid.y);
      if (dragId) { els.get(dragId) && els.get(dragId).classList.remove('drag'); dragId = null; }
      drag = null; return;
    }
    var noteEl = e.target.closest('.note');
    if (noteEl && !readOnly) {
      var id = noteEl.dataset.id, n = notes.get(id);
      drag = { type: 'note', id: id, sx: e.clientX, sy: e.clientY, ox: n.x, oy: n.y, moved: false };
    } else if (noteEl) {
      drag = { type: 'tap', id: noteEl.dataset.id, sx: e.clientX, sy: e.clientY, moved: false };
    } else {
      drag = { type: 'pan', sx: e.clientX, sy: e.clientY, vx: view.x, vy: view.y, moved: false };
    }
  });
  board.addEventListener('pointermove', function (e) {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && ptrs.size >= 2) {
      var p = Array.from(ptrs.values());
      var d = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y) || 1;
      var mx = (p[0].x + p[1].x) / 2, my = (p[0].y + p[1].y) / 2, r = board.getBoundingClientRect();
      var k = clamp(pinch.k0 * d / pinch.d0, MINK, MAXK);
      view.k = k; view.x = mx - r.left - pinch.w.x * k; view.y = my - r.top - pinch.w.y * k;
      applyView(); return;
    }
    if (!drag) return;
    var dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if (!drag.moved && Math.hypot(dx, dy) > 4) {
      drag.moved = true;
      if (drag.type === 'note') { dragId = drag.id; var el = els.get(drag.id); el.classList.add('drag'); var n0 = notes.get(drag.id); n0.z = ++maxZ; el.style.zIndex = n0.z; }
      if (drag.type === 'pan') board.classList.add('panning');
    }
    if (!drag.moved) return;
    if (drag.type === 'note') {
      var n = notes.get(drag.id);
      n.x = Math.round(drag.ox + dx / view.k); n.y = Math.round(drag.oy + dy / view.k);
      var el2 = els.get(drag.id); el2.style.left = n.x + 'px'; el2.style.top = n.y + 'px';
      drawMini();
    } else if (drag.type === 'pan') {
      view.x = drag.vx + dx; view.y = drag.vy + dy; applyView();
    }
  });
  function endPtr(e) {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.delete(e.pointerId);
    if (pinch) { if (ptrs.size < 2) pinch = null; drag = null; return; }
    var d = drag; drag = null;
    board.classList.remove('panning');
    if (!d) return;
    if (d.type === 'note') {
      var el = els.get(d.id); el && el.classList.remove('drag'); dragId = null;
      if (d.moved) { var n = notes.get(d.id); if (n) persist(d.id, { x: n.x, y: n.y, z: n.z }); }
      else if (e.type === 'pointerup') select(d.id, false);
    } else if (d.type === 'tap') {
      if (!d.moved && e.type === 'pointerup') select(d.id, false);
    } else if (d.type === 'pan' && !d.moved && e.type === 'pointerup') {
      deselect();
    }
  }
  board.addEventListener('pointerup', endPtr);
  board.addEventListener('pointercancel', endPtr);
  board.addEventListener('wheel', function (e) {
    e.preventDefault();
    zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * (e.ctrlKey ? 0.012 : 0.0016)));
  }, { passive: false });
  board.addEventListener('dblclick', function (e) {
    if (e.target.closest('.note') || e.target.closest('.hint')) return;
    var p = worldPoint(e.clientX, e.clientY);
    createNote(p.x - NOTE_W / 2, p.y - 30);
  });

  /* ---------- dossiers : le tiroir d'accueil (home.js) les affiche, le mur en montre un ---------- */
  /* dossiers vivants (hors corbeille), archivés compris, dans l'ordre du tiroir */
  function sortedFolders() {
    return Array.from(folders.values()).filter(function (f) { return !f.deletedAt; })
      .sort(function (a, b) { return a.order - b.order || a.name.localeCompare(b.name, 'fr'); });
  }
  /* intercalaires jetés un par un ; ceux partis avec leur tiroir sont listés avec le tiroir */
  function trashedFolders() {
    return Array.from(folders.values()).filter(function (f) { var p = projects.get(f.trashedWith); return f.deletedAt && !(p && p.deletedAt); });
  }
  function trashedProjects() { return Array.from(projects.values()).filter(function (p) { return p.deletedAt; }); }
  function folderCount(fid) {
    var c = 0;
    notes.forEach(function (n) {
      if (fid === 'trash') { if (n.deletedAt) c++; return; }
      if (!n.deletedAt && (fid === 'all' || (fid === 'none' ? !folderOf(n) : n.folder === fid))) c++;
    });
    return c;
  }
  var hubCb = null, hubSubs = [];
  function renderFolders() {
    $('fActs').hidden = !(liveFolder(cur) && isAdmin());
    renderTrashFolders();
    if (hubCb) hubCb();
  }
  function switchFolder(fid) {
    if (sel) deselect();
    cur = fid;
    var sv = null;
    try { sv = JSON.parse(localStorage.getItem('tiroir-view:' + fid) || 'null'); } catch (e) {}
    renderAll();
    if (sv && isFinite(sv.x) && isFinite(sv.y) && isFinite(sv.k)) { view = { x: sv.x, y: sv.y, k: clamp(sv.k, MINK, MAXK) }; applyView(); }
    else fitAll(false);
  }
  function saveFolder(fid, data) {
    var body = { name: data.name, order: data.order };
    if (data.project !== undefined) body.project = data.project;
    return enqueue(fid, function () { return api(data._new ? 'PUT' : 'PATCH', '/api/folders/' + fid, body); });
  }
  function cleanName(v) { return String(v || '').replace(/\s+/g, ' ').trim().slice(0, 40); }
  function newId(prefix) { return prefix + Date.now().toString(36) + Math.floor(Math.random() * 1296).toString(36); }
  /* nouvel intercalaire, dans le tiroir ouvert (ou dans « project » si précisé) */
  function createFolder(name, project) {
    name = cleanName(name);
    if (!name) return null;
    var pid = project === undefined ? curProject : project;
    var order = 0; folders.forEach(function (f) { if (f.project === pid) order = Math.max(order, f.order + 1); });
    var fid = newId('f');
    folders.set(fid, { id: fid, name: name, order: order, project: pid });
    saveFolder(fid, { name: name, order: order, project: pid, _new: true });
    renderAll();
    return fid;
  }

  /* ---------- projets : les tiroirs du meuble (cabinet.js) ---------- */
  var DEFAULT_TABS = [T('général'), 'docs', T('idées')], INBOX = 'parrivees';
  function sortedProjects() {
    return Array.from(projects.values()).filter(function (p) { return !p.deletedAt; })
      .sort(function (a, b) { return a.order - b.order || a.name.localeCompare(b.name, 'fr'); });
  }
  function liveProject(pid) { var p = projects.get(pid); return !!p && !p.deletedAt; }
  function projectFolders(pid) { return sortedFolders().filter(function (f) { return f.project === pid; }); }
  function projectCount(pid) {
    var ids = new Set(projectFolders(pid).map(function (f) { return f.id; }));
    var c = 0; notes.forEach(function (n) { if (!n.deletedAt && ids.has(n.folder)) c++; });
    return c;
  }
  /* intercalaires dont le tiroir n'existe pas (ou plus) : ils restent visibles dans un tiroir « sans tiroir » */
  function orphanCount() {
    return sortedFolders().filter(function (f) { return !liveProject(f.project); }).length;
  }
  function saveProject(pid, data, isNew) {
    return enqueue(pid, function () { return api(isNew ? 'PUT' : 'PATCH', '/api/projects/' + pid, data); });
  }
  function createProject(name) {
    name = cleanName(name);
    if (!name || !isAdmin()) return null;
    var order = 0; projects.forEach(function (p) { if (p.order < 1e5) order = Math.max(order, p.order + 1); });
    var pid = newId('p');
    projects.set(pid, { id: pid, name: name, order: order });
    saveProject(pid, { name: name, order: order }, true);
    DEFAULT_TABS.forEach(function (t) { createFolder(t, pid); });
    return pid;
  }
  /* nouvel ordre des tiroirs (ids dans l'ordre voulu) : on renumérote et on n'envoie que ce qui change */
  function reorderProjects(ids) {
    if (!isAdmin()) return;
    ids.forEach(function (pid, i) {
      var p = projects.get(pid);
      if (!p || p.deletedAt || p.order === i) return;
      projects.set(pid, Object.assign({}, p, { order: i }));
      saveProject(pid, { order: i });
    });
    if (hubCb) hubCb();
  }
  function renameProject(pid, name) {
    var p = projects.get(pid); name = cleanName(name);
    if (!p || !name || !isAdmin() || name === p.name) return;
    projects.set(pid, Object.assign({}, p, { name: name }));
    saveProject(pid, { name: name });
    if (hubCb) hubCb();
  }
  /* archives : le tiroir quitte le meuble pour l'étagère du dessous (contenu intact) ; silent = sans message (retour par glisser) */
  function archiveProject(pid, on, silent) {
    var p = projects.get(pid);
    if (!p || p.deletedAt || !isAdmin() || pid === INBOX || !!p.archived === on) return;
    projects.set(pid, Object.assign({}, p, { archived: on }));
    saveProject(pid, { archived: on });
    if (hubCb) hubCb();
    if (!silent) toast(T(on ? 'tiroir « {name} » rangé aux archives' : 'tiroir « {name} » remis dans le meuble', { name: p.name }), T('Annuler'), function () { archiveProject(pid, !on, true); });
  }
  /* un tiroir part à la corbeille d'un coup, avec ses intercalaires et leurs notes (restaurables ensemble 30 jours) */
  function deleteProject(pid) {
    var p = projects.get(pid);
    if (!p || p.deletedAt || !isAdmin() || pid === INBOX) return false;
    var now = Date.now(), gone = new Set();
    projects.set(pid, Object.assign({}, p, { deletedAt: now }));
    folders.forEach(function (f) {
      if (f.project === pid && !f.deletedAt) { gone.add(f.id); folders.set(f.id, Object.assign({}, f, { deletedAt: now, trashedWith: pid })); }
    });
    notes.forEach(function (n) { if (gone.has(n.folder) && !n.deletedAt) { n.deletedAt = now; n.trashedWith = n.folder; } });
    enqueue(pid, function () { return api('DELETE', '/api/projects/' + pid); });
    renderAll();
    toast(T('tiroir « {name} » mis à la corbeille', { name: p.name }), T('Annuler'), function () { restoreProject(pid); });
    return true;
  }
  function restoreProject(pid) {
    var p = projects.get(pid);
    if (!p || !isAdmin()) return;
    var back = new Set();
    projects.set(pid, Object.assign({}, p, { deletedAt: 0 }));
    folders.forEach(function (f) {
      if (f.trashedWith === pid) { back.add(f.id); folders.set(f.id, Object.assign({}, f, { deletedAt: 0, trashedWith: '' })); }
    });
    notes.forEach(function (n) { if (back.has(n.trashedWith)) { n.deletedAt = 0; n.trashedWith = ''; } });
    enqueue(pid, function () { return api('PATCH', '/api/projects/' + pid, { restore: true }); });
    renderAll();
  }
  function purgeProject(pid) {
    var p = projects.get(pid);
    if (!p || !p.deletedAt || !isAdmin()) return;
    var gone = new Set();
    folders.forEach(function (f) { if (f.project === pid && f.deletedAt) gone.add(f.id); });
    gone.forEach(function (fid) { folders.delete(fid); });
    Array.from(notes.values()).forEach(function (n) { if (gone.has(n.trashedWith)) notes.delete(n.id); });
    projects.delete(pid);
    enqueue(pid, function () { return api('DELETE', '/api/projects/' + pid + '?purge=1'); });
    renderAll();
    toast(T('tiroir « {name} » effacé définitivement', { name: p.name }));
  }
  function renameCurrent() {
    var f = folders.get(cur); if (!f) return;
    var fid = cur, w = $('where');
    editingF = fid;
    var inp = document.createElement('input'); inp.type = 'text'; inp.maxLength = 40; inp.value = f.name; inp.className = 'frename';
    inp.setAttribute('aria-label', T('Nouveau nom du dossier'));
    w.textContent = ''; w.appendChild(inp); inp.focus(); inp.select();
    var done = false;
    function finish(save) {
      if (done) return; done = true; editingF = null;
      var v = cleanName(inp.value);
      if (save && v && v !== f.name) { folders.set(fid, Object.assign({}, f, { name: v })); saveFolder(fid, { name: v, order: f.order }); }
      renderAll();
    }
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') finish(true); else if (e.key === 'Escape') finish(false); });
    inp.addEventListener('blur', function () { finish(true); });
  }
  function armDeleteCurrent(btn) {
    var fid = cur;
    if (!liveFolder(fid)) return;
    if (btn.classList.contains('armed')) {
      btn.classList.remove('armed'); btn.textContent = T('Supprimer');
      goHome();
      trashFolder(fid);
      return;
    }
    btn.classList.add('armed'); btn.textContent = T('Sûr ? (corbeille)');
    setTimeout(function () { btn.classList.remove('armed'); btn.textContent = T('Supprimer'); }, 3000);
  }
  /* corbeille d'un dossier entier : il part avec ses notes, restaurables ensemble pendant 30 jours */
  function trashFolder(fid) {
    var f = folders.get(fid);
    if (!f || f.deletedAt || !isAdmin()) return;
    var now = Date.now();
    folders.set(fid, Object.assign({}, f, { deletedAt: now }));
    notes.forEach(function (n) { if (n.folder === fid && !n.deletedAt) { n.deletedAt = now; n.trashedWith = fid; } });
    enqueue(fid, function () { return api('DELETE', '/api/folders/' + fid); });
    renderAll();
    toast(T('« {name} » mis à la corbeille', { name: f.name }), T('Annuler'), function () { restoreFolder(fid); });
  }
  function restoreFolder(fid) {
    var f = folders.get(fid);
    if (!f || !isAdmin()) return;
    folders.set(fid, Object.assign({}, f, { deletedAt: 0, trashedWith: '' }));
    var p = projects.get(f.project);
    if (p && p.deletedAt) projects.set(p.id, Object.assign({}, p, { deletedAt: 0 })); /* son tiroir revient avec lui */
    notes.forEach(function (n) { if (n.trashedWith === fid) { n.deletedAt = 0; n.trashedWith = ''; } });
    enqueue(fid, function () { return api('PATCH', '/api/folders/' + fid, { restore: true }); });
    renderAll();
  }
  function purgeFolder(fid) {
    var f = folders.get(fid);
    if (!f || !f.deletedAt || !isAdmin()) return;
    folders.delete(fid);
    Array.from(notes.values()).forEach(function (n) { if (n.trashedWith === fid) notes.delete(n.id); });
    enqueue(fid, function () { return api('DELETE', '/api/folders/' + fid + '?purge=1'); });
    renderAll();
    toast(T('« {name} » effacé définitivement', { name: f.name }));
  }
  function archiveFolder(fid, on, silent) {
    var f = folders.get(fid);
    if (!f || !isAdmin() || f.archived === on) return;
    folders.set(fid, Object.assign({}, f, { archived: on }));
    enqueue(fid, function () { return api('PATCH', '/api/folders/' + fid, { archived: on }); });
    renderAll();
    if (!silent) toast(T(on ? '« {name} » rangé dans les archives' : '« {name} » sorti des archives', { name: f.name }), T('Annuler'), function () { archiveFolder(fid, !on, true); });
  }
  /* déplacer un dossier avant un autre (ou à la fin) : on renumérote l'ordre et on n'envoie que ce qui change */
  function moveFolder(fid, beforeId) {
    if (!isAdmin() || !liveFolder(fid) || fid === beforeId) return;
    var pid = folders.get(fid).project;
    var list = sortedFolders().filter(function (f) { return f.id !== fid && f.project === pid; });
    var at = beforeId ? list.findIndex(function (f) { return f.id === beforeId; }) : -1;
    list.splice(at < 0 ? list.length : at, 0, folders.get(fid));
    list.forEach(function (f, i) {
      if (f.order === i) return;
      folders.set(f.id, Object.assign({}, f, { order: i }));
      enqueue(f.id, function () { return api('PATCH', '/api/folders/' + f.id, { order: i }); });
    });
    renderAll();
  }
  /* corbeille : tiroirs entiers puis intercalaires seuls, chacun restaurable ou effaçable (double clic de sécurité) */
  function trashRow(box, name, restore, purge) {
    var row = document.createElement('div'); row.className = 'tf-row';
    var nm = document.createElement('span'); nm.className = 'tf-name'; nm.textContent = name;
    var rs = document.createElement('button'); rs.type = 'button'; rs.className = 'mini-btn'; rs.textContent = T('Restaurer');
    rs.addEventListener('click', restore);
    var del = document.createElement('button'); del.type = 'button'; del.className = 'mini-btn danger'; del.textContent = T('Effacer');
    del.addEventListener('click', function () {
      if (del.classList.contains('armed')) { purge(); return; }
      del.classList.add('armed'); del.textContent = T('Sûr ?');
      setTimeout(function () { del.classList.remove('armed'); del.textContent = T('Effacer'); }, 3000);
    });
    row.appendChild(nm); row.appendChild(rs); row.appendChild(del); box.appendChild(row);
  }
  function trashHead(box, text) {
    var h = document.createElement('div'); h.className = 'lab'; h.textContent = text; box.appendChild(h);
  }
  function renderTrashFolders() {
    var box = $('trashFolders');
    var show = cur === 'trash' && isAdmin();
    var plist = show ? trashedProjects() : [], flist = show ? trashedFolders() : [];
    box.hidden = !plist.length && !flist.length;
    box.textContent = '';
    if (plist.length) {
      trashHead(box, T('Tiroirs dans la corbeille'));
      plist.forEach(function (p) { trashRow(box, p.name, function () { restoreProject(p.id); }, function () { purgeProject(p.id); }); });
    }
    if (flist.length) {
      trashHead(box, T('Intercalaires dans la corbeille'));
      flist.forEach(function (f) { trashRow(box, f.name, function () { restoreFolder(f.id); }, function () { purgeFolder(f.id); }); });
    }
  }
  function fillFolderSelect(val) {
    var s = $('fFolder'); s.textContent = '';
    if (!me.folders) { var o = document.createElement('option'); o.value = ''; o.textContent = T('Sans dossier'); s.appendChild(o); }
    /* intercalaires groupés par tiroir : on peut ranger une note dans n'importe quel projet */
    var groups = sortedProjects().map(function (p) { return { name: p.name, list: projectFolders(p.id) }; });
    var orphans = sortedFolders().filter(function (f) { return !liveProject(f.project); });
    if (orphans.length) groups.push({ name: T('sans tiroir'), list: orphans });
    groups.forEach(function (g) {
      if (!g.list.length) return;
      var og = document.createElement('optgroup'); og.label = g.name;
      g.list.forEach(function (f) { var op = document.createElement('option'); op.value = f.id; op.textContent = f.name; og.appendChild(op); });
      s.appendChild(og);
    });
    s.value = val;
  }

  /* ---------- navigation : meuble (cabinet) -> tiroir d'un projet (home) -> mur d'un intercalaire (wall),
     avec l'historique du navigateur : #/ , #/p/<projet> , #/f/<dossier> ---------- */
  var ORPHANS = '-'; /* tiroir virtuel des intercalaires sans projet connu */
  function mode() { return document.body.dataset.mode || 'cabinet'; }
  function setMode(m) {
    if (m !== 'wall' && sel) deselect();
    document.body.dataset.mode = m;
    if (m === 'wall') requestAnimationFrame(function () { drawMini(); });
    if (hubCb) hubCb();
  }
  function projectOf(fid) {
    var f = folders.get(fid);
    if (!f) return '';
    return liveProject(f.project) ? f.project : ORPHANS;
  }
  function route() {
    var m = /^#\/(all|none|trash|f\/([A-Za-z0-9_-]{1,40})|p\/([A-Za-z0-9_-]{1,40}))$/.exec(location.hash);
    if (!m || (m[1] === 'trash' && !isAdmin())) { curProject = ''; setMode('cabinet'); return; }
    if (m[3]) { curProject = m[3]; setMode('home'); return; }
    if (m[2]) curProject = projectOf(m[2]) || curProject;
    setMode('wall');
    switchFolder(m[2] || m[1]);
  }
  function go(h) {
    if (location.hash !== h && !(h === '' && !location.hash)) history.pushState(null, '', h || location.pathname + location.search);
    route();
  }
  function openFolder(fid) { go(fid === 'all' || fid === 'none' || fid === 'trash' ? '#/' + fid : '#/f/' + fid); }
  function openProject(pid) { go('#/p/' + pid); }
  function goCabinet() { go(''); }
  /* « ← » depuis un mur : on revient au tiroir de son projet ; depuis « tout » / « corbeille » : au meuble */
  function goHome() {
    var pid = liveFolder(cur) ? projectOf(cur) : '';
    if (pid) openProject(pid); else goCabinet();
  }
  function logout() {
    fetch('/logout', { method: 'POST', credentials: 'same-origin', headers: { 'X-Tiroir': '1' } }).then(function () { location.href = '/'; });
  }
  window.addEventListener('popstate', route);
  function inCurrent(f) { return curProject === ORPHANS ? !liveProject(f.project) : f.project === curProject; }
  window.ndsHub = {
    folders: function () {
      return sortedFolders().filter(inCurrent).map(function (f) { return { id: f.id, name: f.name, count: folderCount(f.id), archived: !!f.archived }; });
    },
    projects: function () {
      var list = sortedProjects().map(function (p) { return { id: p.id, name: p.name, count: projectCount(p.id), tabs: projectFolders(p.id).length, archived: !!p.archived }; });
      if (orphanCount()) list.push({ id: ORPHANS, name: T('sans tiroir'), count: 0, tabs: orphanCount(), virtual: true });
      return list;
    },
    project: function () {
      if (curProject === ORPHANS) return { id: ORPHANS, name: T('sans tiroir'), virtual: true };
      var p = projects.get(curProject);
      return p && !p.deletedAt ? { id: p.id, name: p.name } : null;
    },
    openProject: openProject,
    cabinet: goCabinet,
    createProject: createProject,
    renameProject: renameProject,
    reorderProjects: reorderProjects,
    deleteProject: deleteProject,
    archiveProject: archiveProject,
    trashFolder: trashFolder,
    archiveFolder: archiveFolder,
    moveFolder: moveFolder,
    total: function () { return folderCount('all'); },
    trash: function () { return folderCount('trash'); },
    trashAny: function () { return folderCount('trash') + trashedProjects().length + trashedFolders().length; },
    role: function () { return me.role; },
    label: function () { return me.label; },
    none: function () { return folderCount('none'); },
    ready: function () { return inited; },
    mode: mode,
    open: openFolder,
    create: function (name) { return createFolder(name, curProject === ORPHANS ? '' : curProject); },
    logout: logout,
    /* plusieurs vues écoutent le hub (tiroir, meuble) */
    subscribe: function (cb) {
      hubSubs.push(cb);
      hubCb = function () { hubSubs.forEach(function (f) { f(); }); };
      cb();
    }
  };

  /* ---------- carte ---------- */
  function drawMini() {
    var c = mini, r = c.getBoundingClientRect(); if (!r.width) return;
    var dpr = window.devicePixelRatio || 1;
    if (c.width !== Math.round(r.width * dpr)) { c.width = Math.round(r.width * dpr); c.height = Math.round(r.height * dpr); }
    var g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, r.width, r.height);
    var cs = getComputedStyle(document.documentElement), css = function (v) { return cs.getPropertyValue(v).trim() || '#888'; };
    var br = board.getBoundingClientRect();
    var vx0 = -view.x / view.k, vy0 = -view.y / view.k, vw = br.width / view.k, vh = br.height / view.k;
    var bb = bounds() || { x0: vx0, y0: vy0, x1: vx0 + vw, y1: vy0 + vh };
    var x0 = Math.min(bb.x0, vx0) - 40, y0 = Math.min(bb.y0, vy0) - 40, x1 = Math.max(bb.x1, vx0 + vw) + 40, y1 = Math.max(bb.y1, vy0 + vh) + 40;
    var s = Math.min(r.width / (x1 - x0), r.height / (y1 - y0));
    var ox = (r.width - (x1 - x0) * s) / 2, oy = (r.height - (y1 - y0) * s) / 2;
    mini._m = { x0: x0, y0: y0, s: s, ox: ox, oy: oy };
    var colors = { todo: css('--accent'), doing: css('--warn'), done: css('--ok'), info: css('--t3') };
    visibleNotes().forEach(function (n) {
      g.fillStyle = colors[n.status]; g.globalAlpha = n.id === sel ? 1 : 0.8;
      g.fillRect(ox + (n.x - x0) * s, oy + (n.y - y0) * s, Math.max(4, NOTE_W * s), Math.max(3, NOTE_H * s * 0.8));
    });
    g.globalAlpha = 1; g.strokeStyle = css('--disp'); g.lineWidth = 1;
    g.strokeRect(ox + (vx0 - x0) * s + .5, oy + (vy0 - y0) * s + .5, vw * s, vh * s);
  }
  function miniGo(e) {
    var m = mini._m; if (!m) return;
    var r = mini.getBoundingClientRect();
    var wx = (e.clientX - r.left - m.ox) / m.s + m.x0, wy = (e.clientY - r.top - m.oy) / m.s + m.y0;
    var br = board.getBoundingClientRect();
    view.x = br.width / 2 - wx * view.k; view.y = br.height / 2 - wy * view.k; applyView();
  }
  var miniDown = false;
  mini.addEventListener('pointerdown', function (e) { miniDown = true; mini.setPointerCapture(e.pointerId); miniGo(e); });
  mini.addEventListener('pointermove', function (e) { if (miniDown) miniGo(e); });
  mini.addEventListener('pointerup', function () { miniDown = false; });

  /* ---------- commandes ---------- */
  function center() { var r = board.getBoundingClientRect(), p = worldPoint(r.left + r.width / 2, r.top + r.height / 2); return p; }
  $('btnNew').addEventListener('click', function () { var p = center(); createNote(p.x - NOTE_W / 2, p.y - 60); });
  $('btnFit').addEventListener('click', function () { fitAll(); });
  $('btnList').addEventListener('click', function () { $('list').classList.toggle('open'); });
  $('zIn').addEventListener('click', function () { var r = board.getBoundingClientRect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, 1.25); });
  $('zOut').addEventListener('click', function () { var r = board.getBoundingClientRect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, 0.8); });
  $('z1').addEventListener('click', function () { var r = board.getBoundingClientRect(), c = center(); animateTo({ x: r.width / 2 - c.x, y: r.height / 2 - c.y, k: 1 }, 220); });
  $('q').addEventListener('input', function (e) { query = e.target.value; renderList(); });
  $('fClose').addEventListener('click', deselect);
  $('fCenter').addEventListener('click', function () { if (sel) focusNote(sel); });
  $('fFolder').addEventListener('change', function (e) {
    if (!sel) return;
    var id = sel; flush(id);
    persist(id, { folder: e.target.value });
    if (!visible(notes.get(id))) deselect();
    renderAll();
  });
  $('fTitle').addEventListener('input', function (e) { if (sel) queuePatch(sel, { title: e.target.value }); });
  $('fBody').addEventListener('input', function (e) { if (sel) queuePatch(sel, { body: e.target.value }); });
  ['fTitle', 'fBody'].forEach(function (i) { $(i).addEventListener('blur', function () { if (sel) flush(sel); }); });
  $('fRestore').addEventListener('click', function () { if (sel) restoreNote(sel); });
  $('fDel').addEventListener('click', function () {
    var b = $('fDel');
    if (b.classList.contains('armed')) { if (sel) deleteNote(sel); resetDel(); return; }
    b.classList.add('armed'); b.textContent = T('Confirmer ?');
    delTimer = setTimeout(resetDel, 3000);
  });
  document.addEventListener('keydown', function (e) {
    if (mode() !== 'wall') return;
    var tag = (e.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA') { if (e.key === 'Escape') e.target.blur(); return; }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'f' || e.key === 'F') fitAll();
    else if (e.key === 'n' || e.key === 'N') { e.preventDefault(); $('btnNew').click(); }
    else if (e.key === 'Escape') { deselect(); $('list').classList.remove('open'); }
    else if (e.key === '/') { e.preventDefault(); $('q').focus(); }
  });
  window.addEventListener('resize', function () { drawMini(); });
  window.addEventListener('beforeunload', function () { if (sel) flush(sel); });
  try { var mq = window.matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', drawMini); } catch (e) {}
  try { new MutationObserver(drawMini).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }); } catch (e) {}

  /* ---------- démarrage ---------- */
  buildSeg();
  try { var sv = JSON.parse(localStorage.getItem('tiroir-view:' + cur) || localStorage.getItem('tiroir-view') || 'null'); if (sv && isFinite(sv.x) && isFinite(sv.y) && isFinite(sv.k)) { view = { x: sv.x, y: sv.y, k: clamp(sv.k, MINK, MAXK) }; savedView = true; } } catch (e) {}
  applyView(); renderAll(); setSync();
  $('btnOut').addEventListener('click', logout);
  $('btnHome').addEventListener('click', goHome);
  $('fRen').addEventListener('click', renameCurrent);
  $('fDelF').addEventListener('click', function (e) { armDeleteCurrent(e.currentTarget); });
  loadMe().then(function () { applyRole(); route(); initApi(); });
})();
