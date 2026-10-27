/* Accueil : le tiroir à intercalaires. Molette, glisser ou flèches = parcourir ; clic = ouvrir le dossier (le mur) ;
   appui long (admin) = sortir le dossier : corbeille, archives ou nouvelle place. */
(function () {
  'use strict';
  var hub = window.ndsHub;
  if (!hub) return;
  var $ = function (id) { return document.getElementById(id); };
  var plane = $('hPlane'), stage = $('hStage');
  var ROW = 54, TAB_H = 34, COLS = [0.36, 0.6, 0.12], COLS_NARROW = [0.5, 0.04, 0.27], MIN_SHEETS = 16;
  var items = [], rows = [], pos = 0, target = 0, maxPos = 0, raf = 0, sig = '', lastMode = '';
  var creating = false, opening = false, snapT = 0, focusI = -1, hasData = false, showArch = false;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function pad3(n) { return String(n).padStart(3, '0'); }
  function clampPos(v) { return Math.max(0, Math.min(maxPos, v)); }

  /* ---------- contenu du tiroir ouvert : intercalaires vides au fond, puis ceux du projet, archives, « + nouvel intercalaire »
     (« tout » et la corbeille vivent sur le meuble) ---------- */
  function buildItems() {
    var list = [];
    var all = hub.folders(), arch = all.filter(function (f) { return f.archived; });
    all.forEach(function (f) { if (!f.archived) list.push({ kind: 'folder', id: f.id, label: f.name, num: pad3(f.count) }); });
    if (arch.length) {
      list.push({ kind: 'div', id: 'arch', label: T('archives') + (showArch ? ' ▾' : ' ▸'), num: pad3(arch.length) });
      if (showArch) arch.forEach(function (f) { list.push({ kind: 'folder', archived: true, id: f.id, label: f.name, num: pad3(f.count) }); });
    }
    if (hub.role() === 'admin') list.push({ kind: 'new', id: 'new', label: T('nouvel intercalaire'), num: '+' });
    /* intercalaires vides au fond pour remplir le tiroir, comme un vrai classeur */
    var cap = Math.floor(((plane.clientHeight || 600) - TAB_H - 10) / ROW) + 3;
    var blanks = [];
    for (var i = list.length; i < Math.max(MIN_SHEETS, cap); i++) blanks.push({ kind: 'blank' });
    return blanks.concat(list);
  }
  function rowEl(it, i) {
    var row = document.createElement('div');
    row.className = 'h-row k-' + it.kind + (it.archived ? ' k-arch' : '');
    var lift = document.createElement('div'); lift.className = 'h-lift';
    var sheet = document.createElement('div'); sheet.className = 'h-sheet';
    lift.appendChild(sheet);
    if (it.kind === 'blank') {
      row.setAttribute('aria-hidden', 'true');
    } else {
      row.setAttribute('role', 'listitem');
      var tab = document.createElement('button'); tab.type = 'button'; tab.className = 'h-tab';
      var cols = window.innerWidth < 640 ? COLS_NARROW : COLS;
      tab.style.left = (cols[i % cols.length] * 100) + '%';
      var num = document.createElement('span'); num.className = 'h-num'; num.textContent = it.num;
      var name = document.createElement('span'); name.className = 'h-name'; name.textContent = it.label;
      tab.appendChild(num); tab.appendChild(name);
      tab.setAttribute('aria-label', it.kind === 'new' ? T('Créer un dossier') : T('Ouvrir {name}, {n} notes', { name: it.label, n: it.num }));
      tab.addEventListener('click', function () { if (!dragMoved && !justCarried) activate(i); });
      tab.addEventListener('focus', function () { setFocus(i); });
      lift.appendChild(tab);
    }
    row.appendChild(lift);
    return row;
  }

  function render(force) {
    var proj = hub.project();
    var s = JSON.stringify([proj, hub.folders(), hub.role(), showArch]);
    $('hLabel').textContent = proj ? proj.name : '';
    var badge = $('hBadge');
    badge.hidden = !document.body.dataset.role || hub.role() === 'admin'; /* rien tant que les droits ne sont pas connus */
    badge.textContent = (hub.role() === 'edit' ? T('invité · édition') : T('invité · lecture')) + (hub.label() ? ' · ' + hub.label() : '');
    if ((s === sig && !force) || creating || opening || carry) return;
    var first = !hasData;
    hasData = hasData || !!proj;
    sig = s;
    items = buildItems();
    plane.textContent = '';
    rows = items.map(function (it, i) { var r = rowEl(it, i); plane.appendChild(r); return r; });
    measure();
    if (first) pos = target = maxPos;
    if (first && hasData && hub.mode() === 'home') enter();
    pos = clampPos(pos); target = clampPos(target);
    place();
  }
  function measure() {
    var h = plane.clientHeight || 600;
    var fit = Math.max(1, Math.floor((h - TAB_H - 10) / ROW));
    maxPos = Math.max(0, items.length - 1 - fit);
  }
  function place() {
    rows.forEach(function (r, i) {
      var y = (i - pos) * ROW;
      r.style.transform = 'translate3d(0,' + y.toFixed(1) + 'px,0)';
    });
  }

  /* ---------- défilement doux ---------- */
  function animate() {
    if (raf) return;
    (function step() {
      var d = target - pos;
      if (reduce || Math.abs(d) < 0.002) { pos = target; place(); raf = 0; return; }
      pos += d * 0.16; place();
      raf = requestAnimationFrame(step);
    })();
  }
  function scrollTo(v) { target = clampPos(v); animate(); }
  function snapSoon() { clearTimeout(snapT); snapT = setTimeout(function () { scrollTo(Math.round(target)); }, 140); }
  stage.addEventListener('wheel', function (e) {
    if (hub.mode() !== 'home') return;
    e.preventDefault();
    var dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
    scrollTo(target + dy / ROW * 0.55);
    snapSoon();
  }, { passive: false });

  var dragY = null, dragPos = 0, dragMoved = false;
  stage.addEventListener('pointerdown', function (e) {
    if (e.target.closest('input')) return;
    dragY = e.clientY; dragPos = target; dragMoved = false;
  });
  window.addEventListener('pointermove', function (e) {
    if (dragY === null) return;
    var dy = e.clientY - dragY;
    if (Math.abs(dy) > 6) dragMoved = true;
    if (dragMoved) { target = pos = clampPos(dragPos - dy / ROW); place(); }
  });
  window.addEventListener('pointerup', function () {
    if (dragY === null) return;
    dragY = null;
    if (dragMoved) { snapSoon(); setTimeout(function () { dragMoved = false; }, 0); }
  });

  /* ---------- clavier, focus ---------- */
  function setFocus(i) {
    focusI = i;
    rows.forEach(function (r, j) { r.classList.toggle('focus', j === i); });
    var fit = items.length - 1 - maxPos;
    if (i < target + 1) scrollTo(i - 1);
    else if (i > target + fit) scrollTo(i - fit);
  }
  function moveFocus(step) {
    var i = focusI < 0 ? items.length : focusI;
    do { i += step; } while (i >= 0 && i < items.length && items[i].kind === 'blank');
    if (i < 0 || i >= items.length) return;
    var tab = rows[i].querySelector('.h-tab');
    if (tab) tab.focus();
  }
  document.addEventListener('keydown', function (e) {
    if (hub.mode() !== 'home' || creating || e.metaKey || e.ctrlKey || e.altKey) return;
    var tg = (e.target && e.target.tagName) || '';
    if (tg === 'INPUT' || tg === 'TEXTAREA' || tg === 'SELECT') return; /* saisie en cours (ex. panneau de partage) */
    if (e.key === 'ArrowDown') { e.preventDefault(); moveFocus(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moveFocus(-1); }
    else if (e.key === 'PageDown') { e.preventDefault(); scrollTo(target + 6); }
    else if (e.key === 'PageUp') { e.preventDefault(); scrollTo(target - 6); }
    else if ((e.key === 'n' || e.key === 'N') && hub.role() === 'admin') { e.preventDefault(); activate(items.length - 1); }
    else if (e.key === 'Escape' || e.key === 'Backspace') { e.preventDefault(); hub.cabinet(); }
  });

  /* ---------- ouvrir un dossier, en créer un ---------- */
  function activate(i) {
    var it = items[i];
    if (!it || it.kind === 'blank' || opening) return;
    if (it.kind === 'new') { startCreate(i); return; }
    if (it.id === 'arch') { showArch = !showArch; render(true); if (showArch) scrollTo(maxPos); return; }
    opening = true;
    rows[i].classList.add('pull');
    stage.classList.add('opening');
    setTimeout(function () {
      hub.open(it.id);
      stage.classList.remove('opening');
      rows[i].classList.remove('pull');
      opening = false;
    }, reduce ? 0 : 380);
  }
  function startCreate(i) {
    var tab = rows[i].querySelector('.h-tab');
    if (!tab || creating) return;
    creating = true;
    setFocus(i);
    var inp = document.createElement('input'); inp.type = 'text'; inp.maxLength = 40; inp.className = 'h-newin';
    inp.placeholder = T('nom de l’intercalaire'); inp.setAttribute('aria-label', T('Nom du nouvel intercalaire'));
    tab.replaceWith(inp);
    inp.style.left = tab.style.left;
    inp.focus();
    var done = false;
    function finish(save) {
      if (done) return; done = true;
      creating = false;
      var fid = save ? hub.create(inp.value) : null;
      render(true);
      if (fid) {
        var j = items.findIndex(function (x) { return x.id === fid; });
        if (j >= 0) { rows[j].classList.add('born'); focusI = j; rows[j].classList.add('focus'); scrollTo(maxPos); }
      }
    }
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') finish(true);
      else if (e.key === 'Escape') finish(false);
      e.stopPropagation();
    });
    inp.addEventListener('blur', function () { finish(!!inp.value.trim()); });
  }

  /* ---------- appui long sur un dossier (admin) : il sort du tiroir ; corbeille à gauche, archives à droite,
     ou reposé entre deux intercalaires pour changer sa place ---------- */
  var PRESS_MS = 420, press = null, carry = null, justCarried = false;
  var home = $('home'), zTrash = $('zTrash'), zArch = $('zArch');
  function zoneAt(x, y) {
    var hit = null;
    [zTrash, zArch].forEach(function (z) {
      var r = z.getBoundingClientRect();
      if (x > r.left - 30 && x < r.right + 30 && y > r.top - 40 && y < r.bottom + 40) hit = z;
    });
    return hit;
  }
  function rowAt(x, y) {
    var els = document.elementsFromPoint(x, y);
    for (var k = 0; k < els.length; k++) {
      var r = els[k].closest && els[k].closest('.h-row');
      if (!r) continue;
      var i = rows.indexOf(r), it = items[i];
      if (it && it.kind === 'folder' && !it.archived && it.id !== carry.it.id) return i;
      if (it && it.kind !== 'blank') return -1;
    }
    return -1;
  }
  function ghostFor(it, rect) {
    var g = document.createElement('div'); g.className = 'h-ghost';
    var tab = document.createElement('div'); tab.className = 'g-tab';
    var num = document.createElement('span'); num.className = 'h-num'; num.textContent = it.num;
    var name = document.createElement('span'); name.className = 'h-name'; name.textContent = it.label;
    tab.appendChild(num); tab.appendChild(name);
    var body = document.createElement('div'); body.className = 'g-body';
    body.textContent = it.num + ' ' + T(it.num === '001' ? 'note' : 'notes');
    g.appendChild(tab); g.appendChild(body);
    g.style.width = Math.max(200, rect.width + 60) + 'px';
    home.appendChild(g);
    return g;
  }
  function moveGhost(x, y, rot) {
    carry.x = x; carry.y = y;
    carry.ghost.style.transform = 'translate3d(' + (x - carry.offX) + 'px,' + (y - carry.offY) + 'px,0) rotate(' + rot + 'deg)';
  }
  function startCarry(i, x, y) {
    var it = items[i], tab = rows[i].querySelector('.h-tab');
    if (!tab || hub.role() !== 'admin') return;
    var rect = tab.getBoundingClientRect();
    carry = { i: i, it: it, home: rect, offX: x - rect.left, offY: y - rect.top, drop: -1, zone: null, lastX: x };
    dragY = null; dragMoved = true;
    carry.ghost = ghostFor(it, rect);
    moveGhost(rect.left + carry.offX, rect.top + carry.offY, 0);
    void carry.ghost.offsetWidth;
    carry.ghost.classList.add('up');
    rows[i].classList.add('out');
    $('zArchLab').textContent = it.archived ? T('désarchiver') : T('archives');
    $('zArchSub').textContent = it.archived ? T('remettre') : T('ranger');
    home.classList.add('carrying');
    if (navigator.vibrate) navigator.vibrate(15);
    moveGhost(x, y, -2);
  }
  function carryMove(x, y) {
    var rot = Math.max(-8, Math.min(8, (x - carry.lastX) * 0.6)) - 2;
    carry.lastX = x;
    moveGhost(x, y, rot);
    var z = zoneAt(x, y);
    if (z !== carry.zone) {
      if (carry.zone) carry.zone.classList.remove('hot');
      carry.zone = z;
      if (z) { z.classList.add('hot'); if (navigator.vibrate) navigator.vibrate(8); }
    }
    carry.ghost.classList.toggle('over', !!z); /* au-dessus d'une zone : le dossier rapetisse pour laisser lire l'étiquette */
    var d = z ? -1 : rowAt(x, y);
    if (d !== carry.drop) {
      if (carry.drop >= 0 && rows[carry.drop]) rows[carry.drop].classList.remove('drop');
      carry.drop = d;
      if (d >= 0) rows[d].classList.add('drop');
    }
    var sr = stage.getBoundingClientRect();
    if (!z && y < sr.top + 70) scrollTo(target - 0.12);
    else if (!z && y > sr.bottom - 40) scrollTo(target + 0.12);
  }
  function endCarry(cancel) {
    var c = carry; carry = null;
    if (!c) return;
    var g = c.ghost, fid = c.it.id, action = null;
    if (!cancel && c.zone === zTrash) action = 'trash';
    else if (!cancel && c.zone === zArch) action = 'arch';
    else if (!cancel && c.drop >= 0) action = 'move';
    if (action === 'trash' || action === 'arch') {
      var zr = c.zone.getBoundingClientRect();
      g.classList.add('into');
      g.style.transform = 'translate3d(' + (zr.left + zr.width / 2 - 40) + 'px,' + (zr.top + zr.height * 0.55) + 'px,0) scale(.25) rotate(' +
        (action === 'trash' ? -18 : 6) + 'deg)';
      c.zone.classList.add('gulp');
    } else if (action !== 'move') {
      g.classList.add('back');
      g.style.transform = 'translate3d(' + c.home.left + 'px,' + c.home.top + 'px,0) rotate(0deg)';
    } else {
      g.classList.add('into');
      g.style.opacity = '0';
    }
    var dropFid = c.drop >= 0 && items[c.drop] ? items[c.drop].id : null;
    justCarried = true;
    setTimeout(function () { justCarried = false; dragMoved = false; }, 60);
    setTimeout(function () {
      g.remove();
      home.classList.remove('carrying');
      [zTrash, zArch].forEach(function (z) { z.classList.remove('hot', 'gulp'); });
      rows.forEach(function (r) { r.classList.remove('out', 'drop'); });
      if (action === 'trash') hub.trashFolder(fid);
      else if (action === 'arch') hub.archiveFolder(fid, !c.it.archived);
      else if (action === 'move') { if (c.it.archived) hub.archiveFolder(fid, false, true); hub.moveFolder(fid, dropFid); }
      render(true);
    }, reduce ? 0 : 340);
  }
  plane.addEventListener('pointerdown', function (e) {
    var tab = e.target.closest('.h-tab');
    if (!tab || e.button !== 0 || hub.role() !== 'admin' || creating || opening) return;
    var i = rows.indexOf(tab.closest('.h-row'));
    if (i < 0 || items[i].kind !== 'folder') return;
    press = { i: i, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, t: setTimeout(function () { var p = press; press = null; if (p) startCarry(p.i, p.x, p.y); }, PRESS_MS) };
    rows[i].classList.add('pressing');
  });
  function cancelPress() {
    if (!press) return;
    clearTimeout(press.t);
    if (rows[press.i]) rows[press.i].classList.remove('pressing');
    press = null;
  }
  window.addEventListener('pointermove', function (e) {
    if (press) {
      if (Math.abs(e.clientY - press.y0) > 6 || Math.abs(e.clientX - press.x0) > 6) cancelPress();
      else { press.x = e.clientX; press.y = e.clientY; }
    }
    if (carry) { e.preventDefault(); carryMove(e.clientX, e.clientY); }
  });
  window.addEventListener('pointerup', function () { cancelPress(); rows.forEach(function (r) { r.classList.remove('pressing'); }); if (carry) endCarry(false); });
  window.addEventListener('pointercancel', function () { cancelPress(); if (carry) endCarry(true); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && carry) { e.stopPropagation(); endCarry(true); } }, true);
  stage.addEventListener('contextmenu', function (e) { if (press || carry) e.preventDefault(); });

  /* ---------- entrée en scène : les intercalaires montent un à un ---------- */
  function enter() {
    if (reduce) return;
    var first = Math.floor(pos);
    rows.forEach(function (r, i) { r.style.setProperty('--d', Math.max(0, i - first) * 28 + 'ms'); });
    plane.classList.add('pre');
    void plane.offsetWidth;
    requestAnimationFrame(function () { plane.classList.remove('pre'); });
  }

  function onHub() {
    var m = hub.mode();
    if (m !== lastMode) {
      lastMode = m;
      if (m === 'home') { render(true); enter(); stage.focus({ preventScroll: true }); }
      return;
    }
    if (m === 'home') render(false);
  }
  window.addEventListener('resize', function () { measure(); pos = clampPos(pos); target = clampPos(target); place(); });
  $('hBack').addEventListener('click', hub.cabinet);
  $('hOut').addEventListener('click', hub.logout);
  $('hShare').addEventListener('click', function () { if (window.ndsShare) window.ndsShare.open(); });
  hub.subscribe(onHub);
})();
