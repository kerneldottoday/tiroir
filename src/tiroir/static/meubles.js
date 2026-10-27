/* Les meubles : plusieurs meubles de tiroirs, chacun avec son nom gravé sur une plaque au-dessus.
   Flèches ‹ › autour du nom (ou flèches du clavier, ou glisser du doigt) = meuble précédent / suivant, en glissant.
   Admin : double-clic sur le nom = renommer, « + » après le dernier = nouveau meuble, « retirer ce meuble » s'il est vide.
   Le tiroir « arrivées » des agents est dans tous les meubles. Le meuble affiché est retenu dans ce navigateur. */
(function () {
  'use strict';
  var hub = window.ndsHub;
  if (!hub) return;
  var $ = function (id) { return document.getElementById(id); };
  var INBOX = 'parrivees', KEY = 'tiroir-cabinet', SLIDE_MS = 240;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var cabinets = new Map(), cur = '', pending = 0, subs = [], editing = false, sliding = false;
  try { cur = localStorage.getItem(KEY) || ''; } catch (e) { cur = ''; }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function list() {
    return Array.from(cabinets.values()).sort(function (a, b) { return a.order - b.order || a.name.localeCompare(b.name, 'fr'); });
  }
  function current() {
    var l = list();
    if (!l.length) return '';
    return cabinets.has(cur) ? cur : l[0].id;
  }
  function index() { var l = list(), c = current(); return l.findIndex(function (x) { return x.id === c; }); }
  function remember(id) { cur = id; try { localStorage.setItem(KEY, id); } catch (e) {} }
  function drawersIn(cid) {
    return hub.projects().filter(function (p) { return !p.virtual && p.id !== INBOX && p.cabinet === cid; }).length;
  }
  function inCurrent(p) {
    if (!cabinets.size || p.virtual || p.id === INBOX) return true;
    return p.cabinet === current();
  }
  function save(cid, method, data) {
    pending++;
    return hub._save('c:' + cid, method, '/api/cabinets/' + cid, data).then(function () { pending--; }, function () { pending--; });
  }
  function cleanName(v) { return String(v || '').replace(/\s+/g, ' ').trim().slice(0, 40); }

  /* ---------- données (chargées avec les notes) ---------- */
  function load(raw) {
    if (pending > 0 || editing) return;
    var next = new Map();
    raw.forEach(function (c) {
      if (c && typeof c.id === 'string') next.set(c.id, { id: c.id, name: String(c.name || '?'), order: Number(c.order) || 0 });
    });
    cabinets = next;
  }
  function create(name) {
    name = cleanName(name);
    if (!name || hub.role() !== 'admin') return '';
    var order = 0; cabinets.forEach(function (c) { order = Math.max(order, c.order + 1); });
    var cid = hub._newId('c');
    cabinets.set(cid, { id: cid, name: name, order: order });
    save(cid, 'PUT', { name: name, order: order });
    return cid;
  }
  function rename(cid, name) {
    var c = cabinets.get(cid); name = cleanName(name);
    if (!c || !name || name === c.name || hub.role() !== 'admin') return;
    cabinets.set(cid, Object.assign({}, c, { name: name }));
    save(cid, 'PATCH', { name: name });
  }
  /* seulement un meuble vide, et jamais le dernier : rien ne se perd avec un meuble */
  function remove(cid) {
    if (cabinets.size <= 1 || drawersIn(cid) || hub.role() !== 'admin') return false;
    var i = index();
    cabinets.delete(cid);
    save(cid, 'DELETE');
    var l = list();
    remember(l[Math.max(0, Math.min(i, l.length - 1))].id);
    return true;
  }
  /* un tiroir passe au meuble voisin (glissé sur une flèche) */
  function moveDrawer(pid, dir) {
    var l = list(), target = l[index() + dir];
    if (!target || pid === INBOX) return false;
    var p = hub.projects().find(function (x) { return x.id === pid; });
    hub.moveProjectTo(pid, target.id);
    hub._toast(T('tiroir « {name} » rangé dans « {c} »', { name: p ? p.name : '', c: target.name }));
    return true;
  }

  /* ---------- la plaque : ‹ nom › et les points ---------- */
  var nav = $('cNav'), plate = $('cName'), prev = $('cPrev'), next = $('cNext'), dots = $('cDots'), drop = $('cDrop');
  var meuble = document.querySelector('#cabinet .c-meuble');
  function render() {
    if (editing) return;
    var l = list(), i = index(), admin = hub.role() === 'admin', last = i === l.length - 1;
    nav.hidden = !l.length || (l.length < 2 && !admin);
    plate.textContent = l.length ? l[i].name : '';
    plate.title = admin ? T('double-clic : renommer') : '';
    prev.disabled = i <= 0;
    next.disabled = last && !admin;
    next.textContent = last && admin ? '+' : '›';
    next.setAttribute('aria-label', last && admin ? T('nouveau meuble') : T('meuble suivant'));
    drop.hidden = !(admin && l.length > 1 && !drawersIn(current()));
    dots.textContent = '';
    dots.hidden = l.length < 2;
    l.forEach(function (c, k) {
      var b = el('button', 'c-dot' + (k === i ? ' on' : ''));
      b.type = 'button';
      b.setAttribute('aria-label', c.name);
      b.addEventListener('click', function () { go(k); });
      dots.appendChild(b);
    });
  }
  /* le meuble part d'un côté, le suivant arrive de l'autre, puis ses tiroirs montent (cabinet.js) */
  function go(k) {
    var l = list(), i = index();
    if (sliding || editing || k === i || k < 0 || k >= l.length) return;
    var dir = k > i ? 1 : -1;
    var swap = function () {
      remember(l[k].id);
      hub._changed();
      subs.forEach(function (f) { f(); });
    };
    if (reduce) { swap(); return; }
    sliding = true;
    meuble.classList.add(dir > 0 ? 'out-left' : 'out-right');
    setTimeout(function () {
      meuble.classList.remove('out-left', 'out-right');
      meuble.classList.add(dir > 0 ? 'from-right' : 'from-left');
      swap();
      void meuble.offsetWidth;
      meuble.classList.remove('from-right', 'from-left');
      sliding = false;
    }, SLIDE_MS);
  }
  function step(dir) {
    var i = index(), l = list();
    if (dir > 0 && i === l.length - 1) { if (hub.role() === 'admin') startCreate(); return; }
    go(i + dir);
  }
  function editPlate(value, placeholder, done) {
    editing = true;
    var inp = el('input', 'c-name-in');
    inp.type = 'text'; inp.maxLength = 40; inp.value = value; inp.placeholder = placeholder;
    inp.setAttribute('aria-label', placeholder);
    plate.replaceWith(inp);
    inp.focus(); inp.select();
    var finished = false;
    function end(ok) {
      if (finished) return;
      finished = true;
      inp.replaceWith(plate);
      editing = false;
      done(ok ? inp.value : '');
      render();
    }
    inp.addEventListener('keydown', function (e) {
      e.stopPropagation();
      if (e.key === 'Enter') end(true);
      else if (e.key === 'Escape') end(false);
    });
    inp.addEventListener('blur', function () { end(!!inp.value.trim()); });
  }
  function startCreate() {
    if (editing) return;
    editPlate('', T('nom du meuble'), function (v) {
      var cid = create(v);
      if (cid) go(list().findIndex(function (c) { return c.id === cid; }));
    });
  }
  plate.addEventListener('dblclick', function () {
    var c = cabinets.get(current());
    if (!c || hub.role() !== 'admin') return;
    editPlate(c.name, T('nom du meuble'), function (v) { if (v) rename(c.id, v); });
  });
  prev.addEventListener('click', function () { step(-1); });
  next.addEventListener('click', function () { step(1); });
  drop.addEventListener('click', function () {
    if (!drop.classList.contains('armed')) {
      drop.classList.add('armed'); drop.textContent = T('sûr ?');
      setTimeout(function () { drop.classList.remove('armed'); drop.textContent = T('retirer ce meuble'); }, 3000);
      return;
    }
    drop.classList.remove('armed'); drop.textContent = T('retirer ce meuble');
    if (remove(current())) { hub._changed(); subs.forEach(function (f) { f(); }); }
  });

  /* clavier ← → et glisser du doigt sur le meuble */
  document.addEventListener('keydown', function (e) {
    if (hub.mode() !== 'cabinet' || editing || e.metaKey || e.ctrlKey || e.altKey) return;
    var tg = (e.target && e.target.tagName) || '';
    if (tg === 'INPUT' || tg === 'TEXTAREA' || tg === 'SELECT' || document.body.classList.contains('c-dragging')) return;
    if (e.key === 'ArrowLeft') { e.preventDefault(); step(-1); }
    else if (e.key === 'ArrowRight' && index() < list().length - 1) { e.preventDefault(); step(1); }
  });
  var swipe = null;
  $('cStage').addEventListener('pointerdown', function (e) {
    swipe = e.pointerType === 'mouse' ? null : { x: e.clientX, y: e.clientY, t: Date.now() };
  });
  window.addEventListener('pointerup', function (e) {
    var s = swipe; swipe = null;
    if (!s || hub.mode() !== 'cabinet' || document.body.classList.contains('c-dragging')) return;
    var dx = e.clientX - s.x, dy = e.clientY - s.y;
    if (Math.abs(dx) > 60 && Math.abs(dx) > 2 * Math.abs(dy) && Date.now() - s.t < 700) go(index() + (dx < 0 ? 1 : -1));
  });

  /* pendant le glisser d'un tiroir (cabinet.js) : quelle flèche est visée ? -1, 1, ou 0 */
  function arrowAt(x, y, pid) {
    if (pid === INBOX) return 0;
    var i = index(), l = list(), hit = 0;
    [[prev, -1], [next, 1]].forEach(function (a) {
      var r = a[0].getBoundingClientRect(), k = i + a[1];
      a[0].classList.remove('hot');
      if (k < 0 || k >= l.length || nav.hidden) return;
      if (x > r.left - 24 && x < r.right + 24 && y > r.top - 24 && y < r.bottom + 24) { hit = a[1]; a[0].classList.add('hot'); }
    });
    return hit;
  }
  function clearArrows() { prev.classList.remove('hot'); next.classList.remove('hot'); }

  window.ndsMeubles = {
    load: load, list: list, current: current, inCurrent: inCurrent, moveDrawer: moveDrawer,
    arrowAt: arrowAt, clearArrows: clearArrows,
    neighbour: function (dir) { var l = list(); return l[index() + dir] || null; },
    onSwitch: function (f) { subs.push(f); }
  };
  hub.subscribe(function () { if (hub.mode() === 'cabinet') render(); });
})();
