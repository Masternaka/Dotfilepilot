# Création des paquets sur GitHub

## Fonctionnement

Le workflow [ci.yml](../.github/workflows/ci.yml) reprend la chaîne de Sambapilot. Il se déclenche lors d’un push, d’une pull request ou manuellement depuis **Actions → Vérifications Dotfilepilot → Run workflow**.

Les quatre étapes s’enchaînent ainsi :

1. **Python** : contrôles de syntaxe, liens et tests sous Python 3.9, 3.12 et 3.14 ; bilan JSON conservé pour chaque version.
2. **GTK4 et Stow réels sur Linux** : outils installés uniquement sur le runner Ubuntu temporaire, interface testée sous Xvfb et test de sauvegarde/restauration avec GNU Stow. Un test natif ignoré fait échouer cette étape.
3. **Distribution Python** : après réussite des deux vérifications, création de l’archive source `.tar.gz` et du wheel `.whl`, contrôle de leur contenu et test du wheel installé dans un environnement temporaire, hors des sources.
4. **Paquet Arch pour Omarchy** : utilisation de l’archive source vérifiée dans un conteneur Arch, construction avec `makepkg` sous un utilisateur sans privilèges, puis installation et vérification du paquet dans ce conteneur jetable.

Les installations du workflow concernent uniquement les runners et conteneurs GitHub. Elles ne modifient pas l’ordinateur utilisé pour développer le projet.

## Télécharger le paquet

Après publication des fichiers du projet sur GitHub et réussite du workflow :

1. Ouvrir le dépôt puis **Actions**.
2. Sélectionner une exécution réussie de **Vérifications Dotfilepilot**.
3. Dans **Artifacts**, télécharger `dotfilepilot-arch-…`.
4. Décompresser l’archive téléchargée pour récupérer le `.pkg.tar.zst`, le `PKGBUILD`, le fichier `COMMIT.txt` et `SHA256SUMS`.

L’artefact `dotfilepilot-python-…` contient les archives Python. Les bilans de tests apparaissent dans `dotfilepilot-tests-python-…` et `dotfilepilot-tests-native-…`. Les artefacts sont configurés pour être conservés **30 jours**, sous réserve de la politique du dépôt GitHub.

La somme SHA-256 lie le paquet à ses fichiers téléchargeables ; `COMMIT.txt` identifie la révision source. Il ne s’agit pas d’une signature cryptographique de publication.

## Installation future sur Omarchy

Une fois le paquet réellement construit et validé, dans le dossier contenant les fichiers téléchargés :

```sh
sha256sum --check SHA256SUMS
sudo pacman -U ./dotfilepilot-*.pkg.tar.zst
```

Examiner la transaction proposée avant de confirmer. Le paquet déclare `python`, `gtk4`, `python-gobject`, `git`, `stow` et `sudo` comme dépendances : pacman peut installer les composants manquants depuis les dépôts configurés. Le lanceur **Dotfilepilot** est fourni dans le menu des applications ; le terminal reste accessible avec `dotfilepilot`.

Installer l’application ne clone aucun dépôt et n’active aucune configuration. Ces opérations se demandent ensuite séparément dans l’application.

## État actuel

Le workflow, les scripts de contrôle, la recette Arch et le lanceur sont présents dans le dépôt local. Aucun push ni lancement GitHub Actions n’a été réalisé par l’assistant. La première construction complète, l’installation Arch et les contrôles GTK/Stow restent à confirmer sur les runners.

Les paquets sont des artefacts de développement. Aucune Release, signature, publication dans un dépôt pacman ni mise à jour automatique n’est configurée. Le modèle suit le fonctionnement actuel de Sambapilot.

La version Python vient de `dotfilepilot/__init__.py` et doit correspondre à celle de `pyproject.toml`. La révision Arch `pkgrel` reprend le numéro d’exécution GitHub. Le script de préparation refuse de remplacer un dossier de construction existant.

Références : [artefacts GitHub](https://github.com/actions/upload-artifact), [téléchargement des artefacts](https://github.com/actions/download-artifact), [documentation makepkg](https://man.archlinux.org/man/makepkg.8.en).
