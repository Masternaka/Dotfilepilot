# Icône de Dotfilepilot

La direction **1 — Dossier lié** a été choisie le 12 novembre 2026 : un dossier bleu cobalt avec deux maillons blancs, pour représenter les fichiers de configuration et leurs liens symboliques.

![Icône retenue](../dotfilepilot/assets/icons/io.github.dotfilepilot.App.png)

## Fichiers conservés

| Fichier | Usage |
| --- | --- |
| [Image choisie](images/dossier-lie-concept.png) | Original généré, conservé comme référence dans les sources. |
| [SVG couleur](../dotfilepilot/assets/icons/io.github.dotfilepilot.App.svg) | Redessin vectoriel simplifié du dossier et des maillons ; ce n’est pas une copie pixel à pixel du PNG. |
| [SVG monochrome](../dotfilepilot/assets/icons/io.github.dotfilepilot.App-symbolic.svg) | Variante symbolique disponible pour GTK. |
| [PNG 512](../dotfilepilot/assets/icons/io.github.dotfilepilot.App.png) | Image principale et secours pour le chargement depuis les sources ou le wheel. |
| Dossiers `16x16`, `24x24`, `32x32`, `48x48`, `64x64`, `128x128`, `256x256`, `1024x1024` sous `dotfilepilot/assets/icons/` | Déclinaisons PNG, sans fond, pour les menus et lanceurs. |

Les PNG sont des réductions directes de l’image choisie, en conservant la transparence. Le fichier 512 est placé à la racine des icônes pour être trouvé sans installation système ; il n’est pas dupliqué dans un dossier `512x512` dans le code source.

## Intégration dans le code et contrôles CI

Le nom commun est `io.github.dotfilepilot.App`. Il est utilisé par l’identifiant GTK, la fenêtre et le champ `Icon` du lanceur. L’application ajoute son dossier d’icônes embarquées au chemin de recherche GTK afin de les retrouver depuis les sources et le wheel.

Les recettes Arch, Debian et Fedora installent le lanceur sous `io.github.dotfilepilot.App.desktop`, les SVG dans le thème `hicolor` et les PNG dans les répertoires correspondant à leurs dimensions. Les assets sont également embarqués dans les distributions Python. Aucun changement du thème ou du bureau de la machine de développement n’est effectué.

Les contrôles des assets dans le wheel, les sources et les paquets installés ont réussi dans l’[exécution GitHub n° 5 du 13 novembre 2026](https://github.com/Masternaka/Dotfilepilot/actions/runs/43431439343). Les tests GTK sous Xvfb ont également confirmé le nom de l’icône et sa découverte par le thème sur les quatre environnements natifs. Les contrôles automatisés ne prouvent pas la lisibilité ni l’association au menu d’un bureau réel ; voir le [bilan de validation](validation.md#validation-github-actions-du-13-novembre-2026).

## Provenance et fabrication

- Concept créé avec le générateur d’images intégré, puis sélectionné par l’utilisateur. Brief : dossier bleu cobalt, maillons intégrés, silhouette lisible en petite taille, fond transparent, aucun texte.
- Original : `exec-f340777d-69cf-4702-8fbf-fa2ff9936416.png`, copié sous `docs/images/dossier-lie-concept.png`.
- SHA-256 de l’original : `766d3ebdd350191a527f9ce211c318439a2e55013c9829258a94c4d0fdea0ec5`.
- SVG redessinés comme fichiers vectoriels autonomes, sans image embarquée, police ou ressource externe.
- PNG exportés avec l’outil macOS `sips` déjà présent, sans installation. Exemple de reproduction depuis la racine :

```sh
sips -z 32 32 docs/images/dossier-lie-concept.png --out dotfilepilot/assets/icons/32x32/io.github.dotfilepilot.App.png
```

L’export du SVG en PNG par `sips` a échoué ; les PNG proviennent donc exclusivement de l’image choisie, pas du redessin SVG. Les dimensions et le canal alpha des PNG 16, 512 et 1024 ont été inspectés. La fabrication du 12 novembre n’avait comporté ni test applicatif ni installation de paquet. Les contrôles de CI réalisés le 13 novembre sont décrits ci-dessus ; le rendu visuel du SVG et des PNG, la lisibilité dans les menus et l’association au lanceur sur les bureaux cibles restent à vérifier manuellement.
