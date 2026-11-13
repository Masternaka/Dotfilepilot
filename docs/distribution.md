# Création des paquets sur GitHub

## Fonctionnement

Le workflow [ci.yml](../.github/workflows/ci.yml) se déclenche lors d’un push, d’une pull request ou manuellement depuis **Actions → Vérifications Dotfilepilot → Run workflow**. Sa configuration ne constitue pas une preuve d’exécution réussie.

1. **Python** : syntaxe, liens et tests sous Python 3.9, 3.12 et 3.14, avec bilans JSON.
2. **GTK4 et Stow** : conteneurs Arch, Debian 13, Fedora 44 et Ubuntu 24.04. La chaîne prépare les outils, vérifie la reconnaissance du système et les paquets installés, puis lance les tests natifs sous Xvfb et un compte sans privilèges. Tout test natif ignoré fait échouer cette étape.
3. **Archives Python** : après réussite des contrôles précédents, construction des sources `.tar.gz` et du wheel `.whl`, contrôle du contenu et essai du wheel installé hors du dépôt.
4. **Paquets natifs** : trois constructions utilisant la même archive source vérifiée, puis installation et contrôle dans les conteneurs jetables correspondants.

| Cible de construction | Recette | Outil | Artefact prévu |
| --- | --- | --- | --- |
| Arch Linux | `packaging/arch/PKGBUILD.in` | makepkg, utilisateur sans privilèges | `dotfilepilot-arch-…` : `.pkg.tar.zst` |
| Debian 13 | `packaging/debian/*.in` | dpkg-buildpackage, utilisateur sans privilèges | `dotfilepilot-debian13-…` : `.deb` |
| Fedora 44 classique | `packaging/fedora/dotfilepilot.spec.in` | rpmbuild, utilisateur sans privilèges | `dotfilepilot-fedora44-…` : `.rpm` |

Les installations du workflow concernent uniquement les environnements GitHub jetables. Elles ne modifient pas la machine de développement. Aucun paquet ne clone un dépôt ni n’active de dotfiles à son installation.

## Préparation des recettes

Les scripts de préparation ne construisent et n’installent rien. Leur sortie doit être un nouveau dossier ; un dossier existant est refusé. Ils copient l’archive choisie et calculent son empreinte. L’archive doit avoir été contrôlée au préalable avec `scripts/check_distribution.py`.

```sh
python3 -B scripts/prepare_arch_build.py --source dist/dotfilepilot-0.1.0.dev0.tar.gz --output /tmp/dotfilepilot-arch --pkgrel 1
python3 -B scripts/prepare_linux_build.py --family debian --source dist/dotfilepilot-0.1.0.dev0.tar.gz --output /tmp/dotfilepilot-debian --release 1
python3 -B scripts/prepare_linux_build.py --family fedora --source dist/dotfilepilot-0.1.0.dev0.tar.gz --output /tmp/dotfilepilot-fedora --release 1
```

La CI contrôle les empreintes des archives et vérifie que `COMMIT.txt` correspond à sa révision. Elle extrait ensuite les sources pour Debian ou les remet aux outils natifs Arch et Fedora. Ces opérations restent à exécuter dans les environnements prévus.

La version Python vient de `dotfilepilot/__init__.py` et doit correspondre à `pyproject.toml`. Debian et RPM utilisent `0.1.0~dev0` pour représenter la version de développement avant `0.1.0` ; les métadonnées Python conservent `0.1.0.dev0`. La révision des paquets reprend le numéro d’exécution GitHub.

## Télécharger les artefacts après validation

Après publication autorisée des fichiers sur GitHub et réussite du workflow :

1. Ouvrir le dépôt, puis **Actions** et l’exécution réussie de **Vérifications Dotfilepilot**.
2. Choisir l’artefact correspondant à la distribution et à la version cible.
3. Décompresser le téléchargement : paquet, recette, `COMMIT.txt` et `SHA256SUMS`.
4. Vérifier les empreintes depuis ce dossier avec `sha256sum --check SHA256SUMS`.

L’artefact `dotfilepilot-python-…` contient les archives Python. Les bilans JSON sont disponibles dans `dotfilepilot-tests-python-…` et `dotfilepilot-tests-native-FAMILLE-…`. La durée prévue est **30 jours**, sous réserve de la politique du dépôt GitHub. Les empreintes ne constituent pas une signature cryptographique de publication.

## Installation future sur un système de test

**Commandes à utiliser seulement après construction et validation des paquets, avec autorisation d’intervenir sur la machine cible.** Ne pas installer un paquet d’une autre distribution ou supposer qu’un RPM Fedora est portable entre toutes les versions Python de Fedora.

| Cible | Commande à examiner avant confirmation |
| --- | --- |
| Arch ou dérivée compatible | `sudo pacman -U ./dotfilepilot-*.pkg.tar.zst` |
| Debian 13 | `sudo apt install ./dotfilepilot_*.deb` |
| Fedora 44 classique | `sudo dnf install ./dotfilepilot-*.rpm` |

Chaque paquet déclare Python, Git, Stow, GTK4, PyGObject et sudo avec les noms adaptés à sa distribution. Le terminal reste autonome lorsqu’il est utilisé depuis les sources avec Python ; les paquets natifs fournissent l’interface complète. Les bibliothèques Python empaquetées sont celles du Python système de la distribution cible.

Examiner la transaction proposée par le gestionnaire. Après installation, le lanceur **Dotfilepilot** ouvre GTK ; `dotfilepilot` reste accessible dans le terminal. Les opérations de clonage, de déploiement et d’annulation demandent ensuite leur propre aperçu et accord explicite.

La reconnaissance des dérivées par `ID_LIKE` ne valide ni leurs versions de paquets ni tous leurs bureaux. Fedora Atomic / OSTree reste exclu, même si un exécutable `dnf` est présent.

## Icône et lanceur

Le lanceur existant dans `packaging/arch/dotfilepilot.desktop` est commun aux trois recettes. Il est installé sous `/usr/share/applications/io.github.dotfilepilot.App.desktop`, avec `Icon=io.github.dotfilepilot.App`, en cohérence avec l’identifiant GTK. Pour Debian et Fedora, `scripts/stage_desktop.py` copie les fichiers dans la racine de construction explicite, sans remplacer un fichier existant. Il n’est pas un installateur destiné au système réel.

Les icônes couleur et symbolique rejoignent `hicolor`, avec neuf tailles PNG de 16 à 1024 pixels. Les mêmes assets sont embarqués dans le wheel ; l’original de conception reste hors du wheel. Voir la [fiche de l’icône](icone.md). Le rendu et l’association au bureau restent à vérifier après installation autorisée.

## État et première reprise

Les adaptateurs système, recettes et jobs CI sont présents localement. Les tests ordinaires et la préparation des recettes sur fixtures ont été exécutés ; **aucun nouveau workflow GitHub ni paquet natif n’a été construit ou installé dans cette adaptation**. Le [bilan de validation](validation.md) contient les résultats précis.

Première reprise : après demande explicite de publication, pousser les modifications et examiner la matrice native, puis les constructions et contrôles d’installation. Corriger les erreurs à partir des journaux réels. Une exécution réussie ne remplace pas les essais sur bureaux ou machines virtuelles des distributions ciblées, notamment les confirmations sudo et les installations de dépendances.

Les recettes restent des artefacts de développement : aucune licence n’a été choisie. Debian utilise une identité de maintien de développement avec une adresse réservée `example.invalid` ; le champ RPM `License: Unspecified` décrit l’absence de décision et n’accorde aucun droit. Ces métadonnées devront être décidées avant toute soumission officielle ou publication publique. Aucune Release, signature, publication dans un dépôt de paquets ou mise à jour automatique n’est configurée.

Références : [construction Python Debian](https://wiki.debian.org/Python/Pybuild), [plugin pyproject Debian](https://wiki.debian.org/Python/PybuildPluginPyproject), [manuel RPM](https://rpm.org/documentation), [makepkg](https://man.archlinux.org/man/makepkg.8.en), [artefacts GitHub](https://github.com/actions/upload-artifact).
