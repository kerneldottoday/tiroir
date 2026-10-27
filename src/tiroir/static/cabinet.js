/* Le meuble : un tiroir par projet, vu de face. Clic = le tiroir sort puis s'ouvre sur ses intercalaires (home.js).
   Admin : « + nouveau tiroir », double-clic sur l'étiquette = renommer, « retirer » sur un tiroir vide. */
(function () {
  'use strict';
  var hub = window.ndsHub;
  if (!hub) return;
  var $ = function (id) { return document.getElementById(id); };
  var grid = $('cGrid'), extra = $('cExtra'), stage = $('cStage');
  var sig = '', opening = false, creating = false, lastMode = '', drag = null, justDragged = false;
  var hasData = false, lastPid = '', meuble = stage.querySelector('.c-meuble');
  var cab = $('cabinet'), shelf = $('cShelf'), shelfGrid = $('cShelfGrid'), zTrash = $('cZTrash'), zArch = $('cZArch'), showArch = false;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var INBOX = 'parrivees';

  function pad3(n) { return String(n).padStart(3, '0'); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function plural(n, one, many) { return n + ' ' + T(n === 1 ? one : many); }

  /* ---------- un tiroir : étiquette jaune, porte-fiche, numéro noir, poignée ---------- */
  function drawerEl(p, i) {
    var d = el('div', 'c-drawer' + (p.id === INBOX ? ' is-inbox' : '') + (p.virtual ? ' is-virtual' : '') + (p.archived ? ' is-arch' : ''));
    d.setAttribute('role', 'listitem');
    if (!p.virtual) d.dataset.pid = p.id;
    d.style.setProperty('--d', (i * 45) + 'ms');
    var face = el('button', 'c-face');
    face.type = 'button';
    face.setAttribute('aria-label', T('Ouvrir le tiroir {name}', { name: p.name }) + ', ' + plural(p.count, 'note', 'notes'));
    var plate = el('span', 'c-plate', p.name);
    var holder = el('span', 'c-holder');
    holder.appendChild(el('span', 'c-h1', plural(p.count, 'note', 'notes')));
    holder.appendChild(el('span', 'c-h2', plural(p.tabs, 'intercalaire', 'intercalaires')));
    var tag = el('span', 'c-tag', pad3(i + 1));
    var hw = el('span', 'c-hw');
    hw.appendChild(el('span', 'c-lock'));
    hw.appendChild(el('span', 'c-handle'));
    face.appendChild(plate); face.appendChild(holder); face.appendChild(tag); face.appendChild(hw);
    face.addEventListener('click', function () { if (!justDragged) open(d, p); });
    if (hub.role() === 'admin' && !p.virtual) {
      plate.title = T('double-clic : renommer');
      plate.addEventListener('dblclick', function (e) { e.stopPropagation(); rename(d, p, plate); });
    }
    d.appendChild(face);
    if (hub.role() === 'admin' && !p.virtual && p.id !== INBOX) d.appendChild(removeBtn(p));
    return d;
  }
  /* « retirer » : 1er clic = confirmation, 2e clic = le tiroir part à la corbeille avec tout son contenu (Annuler possible) */
  function removeBtn(p) {
    var rm = el('button', 'c-rm', T('retirer'));
    rm.type = 'button';
    rm.setAttribute('aria-label', T('Mettre le tiroir {name} à la corbeille', { name: p.name }));
    var t = 0;
    rm.addEventListener('click', function (e) {
      e.stopPropagation();
      if (rm.classList.contains('armed')) { clearTimeout(t); hub.deleteProject(p.id); return; }
      rm.classList.add('armed');
      rm.textContent = p.count ? T('sûr ? {n} → corbeille', { n: plural(p.count, 'note', 'notes') }) : T('sûr ? → corbeille');
      t = setTimeout(function () { rm.classList.remove('armed'); rm.textContent = T('retirer'); }, 3000);
    });
    return rm;
  }
  function newDrawerEl(i) {
    var d = el('div', 'c-drawer is-new');
    d.style.setProperty('--d', (i * 45) + 'ms');
    var face = el('button', 'c-face');
    face.type = 'button';
    face.setAttribute('aria-label', T('Ajouter un tiroir (un projet)'));
    face.appendChild(el('span', 'c-plate', T('+ nouveau tiroir')));
    var hw = el('span', 'c-hw'); hw.appendChild(el('span', 'c-handle'));
    face.appendChild(hw);
    face.addEventListener('click', function () { startCreate(d, face); });
    d.appendChild(face);
    return d;
  }

  function render(force) {
    var all = hub.projects();
    var list = all.filter(function (p) { return !p.archived; }), arch = all.filter(function (p) { return p.archived; });
    if (!arch.length) showArch = false;
    var admin = hub.role() === 'admin';
    var s = JSON.stringify([all, hub.total(), hub.trashAny(), hub.role(), showArch]);
    var badge = $('cBadge');
    badge.hidden = !document.body.dataset.role || admin;
    badge.textContent = (hub.role() === 'edit' ? T('invité · édition') : T('invité · lecture')) + (hub.label() ? ' · ' + hub.label() : '');
    if ((s === sig && !force) || opening || creating || drag) return;
    /* les données arrivent après le 1er affichage : c'est à ce moment-là que le meuble fait son entrée */
    var first = !hasData && all.length > 0;
    hasData = hasData || all.length > 0;
    sig = s;
    grid.textContent = '';
    list.forEach(function (p, i) { grid.appendChild(drawerEl(p, i)); });
    if (admin) grid.appendChild(newDrawerEl(list.length));
    shelf.hidden = !showArch;
    shelfGrid.textContent = '';
    if (showArch) arch.forEach(function (p, i) { shelfGrid.appendChild(drawerEl(p, i)); });
    renderExtra(admin, arch.length);
    if (first && hub.mode() === 'cabinet') enter();
  }
  /* sous le meuble : « tout », les archives (étagère dépliable) et la corbeille, en onglets noirs comme dans le tiroir */
  function renderExtra(admin, nArch) {
    extra.textContent = '';
    $('cZArchLab').textContent = T('archives');
    $('cZArchSub').textContent = nArch ? plural(nArch, 'tiroir', 'tiroirs') : T('ranger');
    var items = [{ id: 'all', label: T('tout'), n: hub.total() }];
    if (nArch) items.push({ id: 'arch', label: showArch ? 'archives ▾' : 'archives ▸', n: nArch });
    if (admin && hub.trashAny()) items.push({ id: 'trash', label: 'corbeille', n: hub.trash() });
    items.forEach(function (it) {
      var b = el('button', 'c-tab');
      b.type = 'button';
      if (it.id === 'arch') b.setAttribute('aria-expanded', String(showArch));
      b.appendChild(el('span', 'h-num', pad3(it.n)));
      b.appendChild(el('span', 'h-name', it.label));
      b.addEventListener('click', function () { if (it.id === 'arch') toggleArch(); else hub.open(it.id); });
      extra.appendChild(b);
    });
  }
  /* l'étagère des archives se déplie sous le meuble, ses tiroirs descendent un à un */
  function toggleArch() {
    showArch = !showArch;
    render(true);
    if (!showArch || reduce) return;
    shelfGrid.classList.add('pre');
    void shelfGrid.offsetWidth;
    requestAnimationFrame(function () {
      shelfGrid.classList.remove('pre');
      shelf.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }

  /* ---------- ouvrir : le tiroir sort vers toi, les autres s'effacent, puis on entre dedans ---------- */
  function open(d, p) {
    if (opening || creating) return;
    opening = true;
    d.classList.add('pull');
    stage.classList.add('opening');
    setTimeout(function () {
      hub.openProject(p.id);
      d.classList.remove('pull');
      stage.classList.remove('opening');
      opening = false;
    }, reduce ? 0 : 420);
  }

  function inputFor(plate, value, label) {
    var inp = el('input', 'c-in');
    inp.type = 'text'; inp.maxLength = 40; inp.value = value; inp.placeholder = T('nom du projet');
    inp.setAttribute('aria-label', label);
    plate.replaceWith(inp);
    inp.focus(); inp.select();
    return inp;
  }
  function onceDone(inp, finish) {
    var done = false;
    function end(save) { if (done) return; done = true; finish(save, inp.value); }
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') end(true);
      else if (e.key === 'Escape') end(false);
      e.stopPropagation();
    });
    inp.addEventListener('blur', function () { end(!!inp.value.trim()); });
    inp.addEventListener('click', function (e) { e.stopPropagation(); });
  }
  function startCreate(d, face) {
    if (creating) return;
    creating = true;
    d.classList.add('editing');
    var inp = inputFor(face.querySelector('.c-plate'), '', T('Nom du nouveau projet'));
    onceDone(inp, function (save, v) {
      creating = false;
      var pid = save ? hub.createProject(v) : null;
      render(true);
      if (pid) {
        var born = grid.children[hub.projects().findIndex(function (p) { return p.id === pid; })];
        if (born) born.classList.add('born');
      }
    });
  }
  function rename(d, p, plate) {
    if (creating) return;
    creating = true;
    d.classList.add('editing');
    var inp = inputFor(plate, p.name, T('Nouveau nom du projet'));
    onceDone(inp, function (save, v) {
      creating = false;
      if (save) hub.renameProject(p.id, v);
      render(true);
    });
  }

  /* ---------- entrée en scène : le meuble se pose, puis les tiroirs montent un à un, comme les intercalaires ---------- */
  function enter() {
    if (reduce || !hasData) return;
    var els = [meuble, grid, extra, zArch, zTrash];
    els.forEach(function (e) { e.classList.add('pre'); });
    void grid.offsetWidth;
    requestAnimationFrame(function () { els.forEach(function (e) { e.classList.remove('pre'); }); });
  }
  /* retour depuis un tiroir : il rentre dans le meuble, les autres reviennent un à un */
  function closeBack(pid) {
    var d = stage.querySelector('.c-drawer[data-pid="' + CSS.escape(pid) + '"]');
    if (reduce || !d) { enter(); return; }
    grid.classList.add('snap');
    d.classList.add('pull');
    stage.classList.add('opening');
    void grid.offsetWidth;
    grid.classList.remove('snap');
    requestAnimationFrame(function () {
      d.classList.add('closing');
      d.classList.remove('pull');
      stage.classList.remove('opening');
      setTimeout(function () { d.classList.remove('closing'); }, 600);
    });
  }
  function onHub() {
    var m = hub.mode();
    if (m === 'home' && hub.project()) lastPid = hub.project().id;
    if (m !== lastMode) {
      var from = lastMode;
      lastMode = m;
      if (m === 'cabinet') { render(true); if (from === 'home' && lastPid) closeBack(lastPid); else enter(); }
      return;
    }
    if (m === 'cabinet') render(false);
  }
  /* au repos, les meubles d'appoint s'ouvrent au clic : l'étagère des archives, la corbeille */
  zArch.addEventListener('click', function () { if (!drag && !justDragged && hub.projects().some(function (p) { return p.archived; })) toggleArch(); });
  zTrash.addEventListener('click', function () { if (!drag && !justDragged && hub.trashAny()) hub.open('trash'); });
  $('cAll').addEventListener('click', function () { hub.open('all'); });
  $('cOut').addEventListener('click', hub.logout);
  $('cShare').addEventListener('click', function () { if (window.ndsShare) window.ndsShare.open(); });

  /* ---------- ranger les tiroirs (admin) : souris = on glisse tout de suite ; doigt = appui long puis on glisse.
     Le tiroir saisi suit le pointeur, sa place reste en pointillés et les autres se poussent en direct (FLIP).
     Pendant le glisser, les archives sortent à gauche et la corbeille à droite ; un tiroir des archives
     reposé dans le meuble y revient. ---------- */
  var MOVE_PX = 6, HOLD_MS = 300;
  function drawers() { return Array.prototype.slice.call(grid.querySelectorAll('.c-drawer[data-pid]')); }
  function flip(mutate) {
    var before = new Map(drawers().map(function (n) { return [n, n.getBoundingClientRect()]; }));
    mutate();
    if (reduce) return;
    before.forEach(function (r, n) {
      if (n === drag.slot) return;
      var a = n.getBoundingClientRect(), dx = r.left - a.left, dy = r.top - a.top;
      if (!dx && !dy) return;
      n.style.transition = 'none';
      n.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
      requestAnimationFrame(function () { n.style.transition = 'transform .22s cubic-bezier(.2,.8,.2,1)'; n.style.transform = ''; });
    });
  }
  function startDrag(d, x, y) {
    var r = d.getBoundingClientRect();
    var ghost = d.cloneNode(true);
    ghost.classList.add('c-ghost');
    ghost.removeAttribute('data-pid');
    ghost.style.width = r.width + 'px';
    document.body.appendChild(ghost);
    var pid = d.dataset.pid;
    drag = { slot: d, ghost: ghost, offX: x - r.left, offY: y - r.top, order: drawers().map(function (n) { return n.dataset.pid; }),
      pid: pid, fromArch: d.parentNode === shelfGrid, zones: pid !== INBOX, zone: null };
    d.classList.add('c-slot');
    document.body.classList.add('c-dragging');
    if (drag.zones) {
      $('cZArchLab').textContent = drag.fromArch ? T('désarchiver') : T('archives');
      $('cZArchSub').textContent = drag.fromArch ? T('remettre') : T('ranger');
      cab.classList.add('carrying');
    }
    if (navigator.vibrate) navigator.vibrate(12);
    moveDrag(x, y);
  }
  function zoneAt(x, y) {
    var hit = null;
    [zTrash, zArch].forEach(function (z) {
      var r = z.getBoundingClientRect();
      if (x > r.left - 30 && x < r.right + 30 && y > r.top - 40 && y < r.bottom + 40) hit = z;
    });
    return hit;
  }
  function closeZones() {
    cab.classList.remove('carrying');
    [zTrash, zArch].forEach(function (z) { z.classList.remove('hot', 'gulp'); });
  }
  function moveDrag(x, y) {
    drag.ghost.style.transform = 'translate3d(' + (x - drag.offX) + 'px,' + (y - drag.offY) + 'px,0) rotate(-1.5deg)';
    var z = drag.zones ? zoneAt(x, y) : null;
    if (z !== drag.zone) {
      if (drag.zone) drag.zone.classList.remove('hot');
      drag.zone = z;
      if (z) { z.classList.add('hot'); if (navigator.vibrate) navigator.vibrate(8); }
      drag.ghost.classList.toggle('over', !!z); /* au-dessus d'une zone : le tiroir rapetisse pour laisser lire l'étiquette */
    }
    if (z) return;
    var hit = document.elementsFromPoint(x, y).map(function (e) { return e.closest && e.closest('.c-drawer[data-pid]'); })
      .find(function (n) { return n && n !== drag.slot && n.parentNode === grid; });
    if (!hit) return;
    var r = hit.getBoundingClientRect(), after = x > r.left + r.width / 2;
    var ref = after ? hit.nextSibling : hit;
    if (ref === drag.slot || ref === drag.slot.nextSibling) return; /* déjà à cette place */
    flip(function () { grid.insertBefore(drag.slot, ref); });
  }
  function endDrag(cancel) {
    var g = drag; drag = null;
    document.body.classList.remove('c-dragging');
    justDragged = true;
    setTimeout(function () { justDragged = false; }, 60);
    var zone = cancel ? null : g.zone;
    if (zone) { dropInZone(g, zone); return; }
    g.ghost.remove();
    g.slot.classList.remove('c-slot');
    closeZones();
    var ids = drawers().map(function (n) { return n.dataset.pid; });
    if (g.fromArch) { /* sorti des archives : reposé dans le meuble = il y revient, à cette place */
      if (!cancel && g.slot.parentNode === grid) { hub.archiveProject(g.pid, false, true); hub.reorderProjects(ids); }
      render(true);
      return;
    }
    if (cancel || ids.join() === g.order.join()) { render(true); return; }
    hub.reorderProjects(ids);
    render(true);
  }
  /* lâché sur une zone : le tiroir est avalé (corbeille) ou rangé (archives), puis l'action part au serveur */
  function dropInZone(g, zone) {
    var zr = zone.getBoundingClientRect();
    g.ghost.classList.add('into');
    g.ghost.style.transform = 'translate3d(' + (zr.left + zr.width / 2 - 40) + 'px,' + (zr.top + zr.height * 0.55) + 'px,0) scale(.22) rotate(' +
      (zone === zTrash ? 18 : -6) + 'deg)';
    zone.classList.add('gulp');
    setTimeout(function () {
      g.ghost.remove();
      g.slot.classList.remove('c-slot');
      closeZones();
      if (zone === zTrash) hub.deleteProject(g.pid);
      else hub.archiveProject(g.pid, !g.fromArch);
      render(true);
    }, reduce ? 0 : 340);
  }
  var press = null;
  stage.addEventListener('pointerdown', function (e) {
    var d = e.target.closest('.c-drawer[data-pid]');
    if (!d || e.button !== 0 || hub.role() !== 'admin' || creating || opening || e.target.closest('.c-rm, .c-in')) return;
    press = { d: d, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, touch: e.pointerType !== 'mouse', held: false };
    if (press.touch) press.t = setTimeout(function () { if (press) { press.held = true; startDrag(press.d, press.x, press.y); } }, HOLD_MS);
  });
  window.addEventListener('pointermove', function (e) {
    if (drag) { e.preventDefault(); moveDrag(e.clientX, e.clientY); return; }
    if (!press) return;
    press.x = e.clientX; press.y = e.clientY;
    var far = Math.abs(e.clientX - press.x0) > MOVE_PX || Math.abs(e.clientY - press.y0) > MOVE_PX;
    if (!far) return;
    if (press.touch) { clearTimeout(press.t); press = null; return; } /* doigt qui bouge avant l'appui long = on fait défiler */
    var p0 = press; press = null;
    startDrag(p0.d, p0.x0, p0.y0);
    moveDrag(e.clientX, e.clientY);
  }, { passive: false });
  window.addEventListener('pointerup', function () {
    if (press) { clearTimeout(press.t); press = null; }
    if (drag) endDrag(false);
  });
  window.addEventListener('pointercancel', function () { if (press) { clearTimeout(press.t); press = null; } if (drag) endDrag(true); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && drag) { e.stopPropagation(); endDrag(true); } }, true);
  stage.addEventListener('contextmenu', function (e) { if (press || drag) e.preventDefault(); });
  stage.addEventListener('dragstart', function (e) { e.preventDefault(); }); /* pas de glisser natif du navigateur */

  hub.subscribe(onHub);
})();
