# Dotfilepilot

Dotfilepilot facilite l’installation et la gestion des fichiers de configuration sur **Omarchy / Arch Linux**. Le projet reprend l’approche de Sambapilot : un moteur Python partagé par le terminal et une interface graphique GTK4.

Cette première version de développement propose le clonage d’un dépôt Git HTTPS, la sélection des configurations, les liens GNU Stow, les sauvegardes des conflits et l’annulation d’un déploiement. **Les tests locaux utilisent un Stow simulé ; l’utilisation réelle sur Omarchy reste à valider.**

## Fonctions présentes dans le code

| Fonction | Comportement | Limite actuelle |
| --- | --- | --- |
| Dépendances | Détecter et proposer `git`, `stow`, `python`, `python-gobject` et `gtk4`, installer après confirmation. | Installation dans le terminal avec `sudo` et confirmation de la transaction pacman. |
| Dépôt | Cloner en HTTPS ou utiliser un dossier existant. | Aucun sous-module, script d’installation ou hook du dépôt lancé ; premier parcours prévu pour les dépôts publics. |
| Inventaire | Afficher les dossiers candidats et cocher les configurations à activer. | Le dépôt doit être organisé par paquets Stow contenant des fichiers cachés. |
| Aperçu | Laisser Stow calculer les liens dans un dossier temporaire, puis examiner les destinations réelles. | Stow doit déjà être installé ; règles Stow personnalisées refusées. |
| Activation | Revalider l’aperçu, sauvegarder les conflits, lancer Stow et vérifier les liens attendus. | Modifications du dossier cible uniquement, sans prise en charge des configurations système. |
| Annulation | Retirer les liens journalisés et restaurer les fichiers sauvegardés. | Un fichier remplacé depuis le déploiement bloque l’annulation ; les répertoires vides peuvent rester. |
| GTK4 | Accueil, dépôt, configurations, sauvegardes et aperçu avec accord explicite. | Interface codée, rendu et interactions natifs non testés ici. |

L’installation de Stow et Git concerne les besoins de Dotfilepilot. Installer Ghostty, Zsh ou les autres applications correspondant aux configurations reste une action distincte, à ajouter ensuite.

## Depuis les sources

Depuis la racine du dépôt, avec Python 3.9 ou ultérieur déjà disponible :

```sh
python3 -B -m dotfilepilot --help
python3 -B -m dotfilepilot diagnostic
```

Sur **Arch / Omarchy**, examiner les dépendances puis demander leur installation :

```sh
python3 -B -m dotfilepilot dependances
python3 -B -m dotfilepilot dependances --appliquer
```

La seconde commande affiche l’aperçu, demande de taper `OUI`, puis lance pacman via `sudo`. Pacman conserve sa propre confirmation sur les dépendances et les éventuels remplacements. Aucune commande d’installation n’est lancée au démarrage. Si Python manque, il doit être installé par le mécanisme de distribution du système ; l’application Python ne peut pas s’amorcer seule.

Ouvrir l’interface lorsque GTK4 et PyGObject sont disponibles :

```sh
python3 -B -m dotfilepilot gui
```

## Exemple de parcours terminal

Adapter l’URL et les chemins. Le dossier parent de la destination du clonage doit déjà exister.

```sh
# Aperçu uniquement
python3 -B -m dotfilepilot cloner https://github.com/PROPRIETAIRE/dotfiles.git ~/dotfiles
# Clonage après confirmation
python3 -B -m dotfilepilot cloner https://github.com/PROPRIETAIRE/dotfiles.git ~/dotfiles --appliquer

python3 -B -m dotfilepilot inventaire ~/dotfiles
python3 -B -m dotfilepilot activer ~/dotfiles ghostty zsh
python3 -B -m dotfilepilot activer ~/dotfiles ghostty zsh --appliquer

python3 -B -m dotfilepilot historique
python3 -B -m dotfilepilot annuler IDENTIFIANT
python3 -B -m dotfilepilot annuler IDENTIFIANT --appliquer
```

Sans `--appliquer`, les commandes d’intervention produisent seulement un aperçu. Les aperçus d’activation utilisent un dossier temporaire privé pour les liens Stow, sans déplacer les configurations existantes. Les interventions sont bloquées hors Arch Linux, même avec `--appliquer`.

Les liens actifs pointent vers le dépôt : modifier leur contenu dans un éditeur modifie donc les fichiers du dépôt. Ne pas déplacer ni supprimer le clone tant que ses configurations sont actives.

## Structure de dépôt acceptée

```text
dotfiles/
├── ghostty/
│   └── .config/ghostty/config
└── zsh/
    └── .zshrc
```

Les dossiers sans fichier caché ne sont pas proposés. Les scripts, modèles système ou autres contenus non cachés à la racine d’un paquet sont bloqués lors de l’analyse, sauf les documents README, LICENSE et COPYING. Un fichier `samba/smb.conf` n’est donc pas automatiquement dirigé vers `/etc/samba/smb.conf`. Les variantes `dot-config`, les sources symboliques et les règles `.stowrc` / `.stow-local-ignore` / `.stow-global-ignore` ne sont pas prises en charge dans cette version.

## Sauvegardes et reprise

Les journaux et sauvegardes sont conservés dans `$XDG_STATE_HOME/dotfilepilot`, ou `~/.local/state/dotfilepilot`. Le dossier doit être privé (`0700`) ; les journaux sont écrits en `0600`. Les fichiers et liens remplacés sont déplacés dans un dossier daté avant Stow. Une annulation conserve les sauvegardes.

Si Stow échoue, le journal reste dans l’état `interrompu`. Consulter `historique`, examiner `annuler IDENTIFIANT`, puis demander l’annulation. Aucun retour arrière silencieux n’est effectué. Les copies sensibles restent locales : ne pas les ajouter à Git. Cette reprise est testée pour les erreurs simulées ; elle ne constitue pas une garantie contre toute panne disque ou coupure d’alimentation.

## Vérification

```sh
make test
make check
# Sur une machine de test avec Stow déjà installé, données temporaires uniquement :
DOTFILEPILOT_TEST_STOW=1 make test
```

Voir le [bilan de validation et la recette Omarchy](docs/validation.md), ainsi que le [cahier des charges et la suite du projet](docs/conception.md).

## Paquets GitHub

Comme Sambapilot, le workflow GitHub Actions prépare les tests Python, GTK4 et Stow, puis construit les archives Python et un paquet Arch `.pkg.tar.zst`. Les paquets vérifiés seront téléchargeables dans les artefacts de chaque exécution réussie, conservés 30 jours. Le paquet Arch déclare les dépendances et fournit le lanceur graphique.

Le [guide de distribution](docs/distribution.md) décrit le téléchargement et l’installation sur Omarchy. La chaîne est configurée localement ; aucune exécution GitHub ni construction Arch n’a encore été vérifiée.

Les commandes retournent `0` en cas de succès ou d’annulation volontaire, `2` pour une erreur et `3` si GTK est indisponible. `--version` affiche la version de développement.
