/* Languages: the interface is written in French (the original); EN translates it.
   Language = localStorage "tiroir-lang" if set, else the browser language (fr* -> French, anything else -> English).
   t('texte {name}', { name: x }) translates then fills {placeholders}; static HTML text and labels are translated on load. */
(function () {
  'use strict';
  var EN = {
    /* states */
    'À faire': 'To do', 'En cours': 'Doing', 'Info': 'Info', 'Fait': 'Done', 'Tout': 'All', 'État': 'Status',
    /* wall */
    'Tous les projets': 'All drawers', 'Sans dossier': 'No tab', 'Corbeille': 'Trash', 'En ligne': 'Online', 'Hors ligne': 'Offline',
    'Connexion': 'Connecting', 'Nouvelle note': 'New note', 'Note effacée définitivement': 'Note deleted for good',
    'Note mise à la corbeille': 'Note moved to the trash', 'Annuler': 'Undo', 'Invité · édition': 'Guest · edit', 'Invité · lecture': 'Guest · read',
    'Sans titre': 'Untitled', 'Aucun résultat': 'No result', 'Rien pour l’instant': 'Nothing yet', 'Effacer définitivement': 'Delete for good',
    'Supprimer': 'Delete', 'Modifiée le {d}': 'Edited {d}', 'Source : {s}': 'Source: {s}', 'Restaurer': 'Restore', 'Effacer': 'Delete',
    'Sûr ?': 'Sure?', 'Sûr ? (corbeille)': 'Sure? (trash)', 'Confirmer ?': 'Confirm?', 'Nouveau nom du dossier': 'New tab name',
    'Tiroirs dans la corbeille': 'Drawers in the trash', 'Intercalaires dans la corbeille': 'Tabs in the trash', 'sans tiroir': 'no drawer',
    '« {name} » mis à la corbeille': '“{name}” moved to the trash', '« {name} » effacé définitivement': '“{name}” deleted for good',
    '« {name} » rangé dans les archives': '“{name}” archived', '« {name} » sorti des archives': '“{name}” unarchived',
    'Liste': 'List', 'Tout voir': 'Fit all', '+ Note': '+ Note', 'Quitter': 'Log out', 'Renommer': 'Rename', 'Fermer': 'Close',
    'Centrer': 'Center', 'Dossier': 'Tab', 'Titre': 'Title', 'Contenu': 'Content', '← Tiroir': '← Drawer', 'Chercher…': 'Search…',
    'dossier vide\ndouble-clic sur le mur, ou « + note »': 'empty tab\ndouble-click on the wall, or “+ note”',
    'Carte du mur : cliquer pour se déplacer': 'Wall map: click to move', 'Chercher une note': 'Search a note', 'Dézoomer': 'Zoom out',
    'Zoomer': 'Zoom in', 'Fiche de la note': 'Note details', 'Filtrer par état': 'Filter by status', 'Liste des notes': 'Notes list',
    'Mur de notes': 'Notes wall', 'Notes enregistrées sur ton serveur': 'Notes saved on your server', 'Ouvrir la liste des notes': 'Open the notes list',
    'Revenir au tiroir des projets': 'Back to the drawer', 'Zoom 100 %': 'Zoom 100%',
    /* drawers and tabs */
    'général': 'general', 'idées': 'ideas', 'tiroir': 'drawer', 'tiroirs': 'drawers', 'intercalaire': 'tab', 'intercalaires': 'tabs',
    'note': 'note', 'notes': 'notes', 'tout': 'all', 'archives': 'archives', 'corbeille': 'trash', 'ranger': 'put away', 'remettre': 'bring back',
    'désarchiver': 'unarchive', 'retirer': 'remove', '30 jours': '30 days', 'partager': 'share', 'quitter': 'log out', '← meuble': '← cabinet',
    'tiroir « {name} » rangé aux archives': 'drawer “{name}” archived', 'tiroir « {name} » remis dans le meuble': 'drawer “{name}” back in the cabinet',
    'tiroir « {name} » mis à la corbeille': 'drawer “{name}” moved to the trash', 'tiroir « {name} » effacé définitivement': 'drawer “{name}” deleted for good',
    'nouvel intercalaire': 'new tab', 'Créer un dossier': 'Create a tab', 'Ouvrir {name}, {n} notes': 'Open {name}, {n} notes',
    'invité · édition': 'guest · edit', 'invité · lecture': 'guest · read', 'nom de l’intercalaire': 'tab name', 'Nom du nouvel intercalaire': 'New tab name',
    'Ouvrir le tiroir {name}': 'Open drawer {name}', 'double-clic : renommer': 'double-click: rename',
    'Mettre le tiroir {name} à la corbeille': 'Move drawer {name} to the trash', 'sûr ? {n} → corbeille': 'sure? {n} → trash', 'sûr ? → corbeille': 'sure? → trash',
    'Ajouter un tiroir (un projet)': 'Add a drawer (a project)', '+ nouveau tiroir': '+ new drawer', 'nom du projet': 'project name',
    'Nom du nouveau projet': 'New project name', 'Nouveau nom du projet': 'New project name',
    'Le meuble : un tiroir par projet': 'The cabinet: one drawer per project', 'Projets': 'Projects', 'Tiroirs archivés': 'Archived drawers',
    'Revenir au meuble': 'Back to the cabinet', 'Tiroir ouvert : les intercalaires du projet': 'Open drawer: the tabs of the project',
    'Dossiers de projets': 'Project tabs',
    /* theme */
    'sombre': 'dark', 'clair': 'light', 'Passer en thème clair': 'Switch to the light theme', 'Passer en thème sombre': 'Switch to the dark theme',
    /* sharing */
    'tous les dossiers': 'every tab', 'aucun dossier (supprimés)': 'no tab (deleted)', 'Copié ✓': 'Copied ✓', 'Copie ce lien :': 'Copy this link:',
    'Partager le Tiroir': 'Share Tiroir', 'fermer': 'close', 'Nom de la personne': 'Name of the person', 'ex. Alex': 'e.g. Alex', 'Accès': 'Access',
    'Lecture': 'Read', 'Édition': 'Edit', 'Dossiers': 'Tabs', 'Tous (y compris les futurs)': 'All (including future ones)', 'Créer le lien': 'Create the link',
    'Liens actifs': 'Active links', 'édition': 'edit', 'lecture': 'read', 'Révoquer': 'Revoke', 'Donne un nom à ce lien.': 'Give this link a name.',
    'Lien créé et copié : envoie-le à {name}.': 'Link created and copied: send it to {name}.', 'Lien révoqué : {name} n’a plus accès.': 'Link revoked: {name} has no access anymore.',
    'Un lien ouvre le Tiroir sans mot de passe. Lecture = consulter ; édition = créer et modifier des post-it. Seul toi peux supprimer.':
      'A link opens Tiroir without the password. Read = look; edit = create and change sticky notes. Only you can delete.'
  };

  var lang = 'fr';
  try { lang = localStorage.getItem('tiroir-lang') || ''; } catch (e) { lang = ''; }
  if (lang !== 'fr' && lang !== 'en') lang = /^fr\b/i.test(navigator.language || '') ? 'fr' : 'en';
  document.documentElement.lang = lang;

  function t(s, vars) {
    var out = lang === 'en' && Object.prototype.hasOwnProperty.call(EN, s) ? EN[s] : s;
    if (vars) Object.keys(vars).forEach(function (k) { out = out.split('{' + k + '}').join(String(vars[k])); });
    return out;
  }
  window.t = t;
  window.T = t;
  window.tiroirLang = lang;

  /* static HTML: text nodes and the labels people read */
  function translatePage() {
    if (lang === 'fr') return;
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (var n = walker.nextNode(); n; n = walker.nextNode()) {
      var key = n.nodeValue.trim();
      if (n.parentElement && n.parentElement.closest('.h-brand, #brand')) continue; /* the name stays « tiroir » */
      if (key && Object.prototype.hasOwnProperty.call(EN, key)) n.nodeValue = n.nodeValue.replace(key, EN[key]);
    }
    ['aria-label', 'placeholder', 'title'].forEach(function (a) {
      document.querySelectorAll('[' + a + ']').forEach(function (el) { el.setAttribute(a, t(el.getAttribute(a))); });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', translatePage);
  else translatePage();
})();
