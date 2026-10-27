/* Thème clair / sombre du Tiroir : chargé en tête de page (avant l'affichage, pas de flash).
   Choix mémorisé dans ce navigateur ; sans choix, on suit le système. Bouton = tout élément [data-theme-toggle]. */
(function () {
  'use strict';
  var KEY = 'tiroir-theme';
  var root = document.documentElement;
  function saved() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function system() { return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }
  function tr(s) { return window.t ? window.t(s) : s; } /* i18n.js, when the page loads it */
  function apply(theme) {
    root.dataset.theme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
      b.textContent = theme === 'dark' ? tr('clair') : tr('sombre');
      b.setAttribute('aria-label', theme === 'dark' ? tr('Passer en thème clair') : tr('Passer en thème sombre'));
    });
  }
  apply(saved() || system());
  document.addEventListener('DOMContentLoaded', function () {
    apply(root.dataset.theme);
    document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
      b.addEventListener('click', function () {
        var t = root.dataset.theme === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem(KEY, t); } catch (e) {}
        apply(t);
      });
    });
  });
  if (window.matchMedia) {
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { if (!saved()) apply(system()); });
  }
})();
