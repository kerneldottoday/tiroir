# tiroir

**Un meuble à tiroirs pour tes post-it, sur ton propre serveur. Tes agents IA peuvent aussi y déposer des notes.**

Un tiroir par projet, des intercalaires dans chaque tiroir, un mur de post-it libre derrière chaque intercalaire.
Quelques fichiers Python, aucune dépendance, aucune base de données : ça s'installe en dix secondes et tout tient dans un fichier JSON qui t'appartient.

![Tiroir : ouvrir un tiroir, choisir un intercalaire, travailler sur le mur](docs/demo.gif)

[English version](README.md)

## Installer

Python 3.10 ou plus récent.

```bash
pipx install git+https://github.com/kerneldottoday/tiroir
tiroir set-password      # 14 caractères minimum ; seule une empreinte scrypt est gardée
tiroir                   # http://127.0.0.1:5950
```

Avec Docker : voir le [README anglais](README.md#docker) et `docker-compose.yml` (HTTPS automatique avec Caddy).
Pour des tiroirs créés en français (« arrivées », « divers », « général / docs / idées ») : `TIROIR_LANG=fr`.
L'interface suit la langue du navigateur.

## Ce que ça fait

- **Le meuble** : un tiroir par projet, qui s'ouvre et se referme en animation. On glisse un tiroir pour le ranger, le poser sur les archives (à gauche) ou la corbeille (à droite).
- **Les intercalaires et le mur** : post-it posés librement, zoom, mini-carte, quatre états, recherche, raccourcis (`N`, `F`, `/`).
- **Les agents** : chaque fichier `<dossier_agents>/<agent>/<note>.md` devient un post-it dans le tiroir « arrivées ». Lecture seule, liens symboliques refusés, taille limitée.
- **Le partage** : liens d'invitation en lecture ou en édition, sur tout ou sur certains intercalaires, révocables d'un clic. Seul l'admin supprime.
- **Corbeille de 30 jours** pour les notes, les intercalaires et les tiroirs entiers, avec « Annuler ».
- **Des données à l'abri** : écriture atomique avec `fsync`, trois sauvegardes tournantes, et un fichier abîmé n'est jamais pris pour un mur vide.

## Réglages, ligne de commande, sécurité

Tout est détaillé dans le [README anglais](README.md#settings). En bref : `tiroir set-password` change le mot de passe
et déconnecte tous les appareils admin, `tiroir export` sort tout le tiroir en JSON, `tiroir logout-all` coupe toutes les sessions.

## Licence

[AGPL-3.0-or-later](LICENSE).
