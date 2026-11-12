# Dotfilepilot

<img src="dotfilepilot/assets/icons/io.github.dotfilepilot.App.png" width="96" height="96" alt="Icône Dotfilepilot : dossier bleu avec deux maillons blancs">

Dotfilepilot facilite l’installation et la gestion des fichiers de configuration sur **Arch Linux et ses distributions dérivées**. Le projet reprend l’approche de Sambapilot : un moteur Python partagé par le terminal et une interface graphique GTK4.

Cette première version de développement propose le clonage d’un dépôt Git HTTPS, la sélection des configurations, les liens GNU Stow, les sauvegardes des conflits et l’annulation d’un déploiement. **Les tests locaux utilisent un Stow simulé ; l’utilisation réelle sur Arch Linux et ses dérivées reste à valider.**

## Fonctions présentes dans le code

| Fonction | Comportement | Limite actuelle |
| --- | --- | --- |
| Dépendances | Détecter et proposer `git`, `stow`, `python`, `python-gobject` et `gtk4`, installer après confirmation. | Installation dans le terminal avec `sudo` et confirmation de la transaction pacman. |
| Dépôt | Cloner en HTTPS ou utiliser un dossier existant. | Aucun sous-module, script d’installation ou hook du dépôt lancé ; premier parcours prévu pour les dépôts publics. |
| Inventaire | Afficher les dossiers candidats et cocher les configurations à activer. | Le dépôt doit être organisé par paquets Stow contenant des fichiers cachés. |
| Aperçu | Laisser Stow calculer les liens dans un dossier temporaire, puis examiner les sources et destinations ; GTK présente un tableau par configuration avec filtres et totaux. | Stow doit déjà être installé ; règles Stow personnalisées refusées. |
| Activation | Revalider l’aperçu, sauvegarder les conflits, lancer Stow et vérifier les liens attendus. | Modifications du dossier cible uniquement, sans prise en charge des configurations système. |
| Annulation | Retirer les liens journalisés et restaurer les fichiers sauvegardés. | Un fichier remplacé depuis le déploiement bloque l’annulation ; les répertoires vides peuvent rester. |
| État actuel | Observer à la demande les liens connus des journaux : corrects, cassés, remplacés, absents ou indisponibles. | Lecture seule, sans inventaire global des dotfiles ni contrôle du contenu des fichiers. |
| État Git | Consulter la branche, la révision et les fichiers modifiés, ajoutés, supprimés ou non suivis. | Lecture locale de la racine du dépôt, sans actualisation distante ; sous-modules ignorés. |
| GTK4 | Accueil, dépôt, configurations, sauvegardes et aperçu avec accord explicite. | Interface codée, rendu et interactions natifs non testés ici. |

L’installation de Stow et Git concerne les besoins de Dotfilepilot. Installer Ghostty, Zsh ou les autres applications correspondant aux configurations reste une action distincte, à ajouter ensuite.

## Depuis les sources

Depuis la racine du dépôt, avec Python 3.9 ou ultérieur déjà disponible :

```sh
python3 -B -m dotfilepilot --help
python3 -B -m dotfilepilot diagnostic
```

Sur **Arch Linux ou une distribution dérivée**, examiner les dépendances puis demander leur installation :

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
python3 -B -m dotfilepilot etat-git ~/dotfiles
python3 -B -m dotfilepilot activer ~/dotfiles ghostty zsh
python3 -B -m dotfilepilot activer ~/dotfiles ghostty zsh --appliquer

python3 -B -m dotfilepilot historique
python3 -B -m dotfilepilot etat
python3 -B -m dotfilepilot annuler IDENTIFIANT
python3 -B -m dotfilepilot annuler IDENTIFIANT --appliquer
```

Sans `--appliquer`, les commandes d’intervention produisent seulement un aperçu. Les aperçus d’activation utilisent un dossier temporaire privé pour les liens Stow, sans déplacer les configurations existantes. Les interventions sont bloquées hors de la famille Arch, même avec `--appliquer`.

La détection exige Linux et un fichier `os-release` indiquant `ID=arch` ou contenant le mot exact `arch` dans `ID_LIKE`. Elle lit `/etc/os-release`, puis `/usr/lib/os-release` si le premier est absent. Aucune liste de distributions n’est imposée. Une identité absente, illisible ou non reconnue reste bloquante ; la présence de pacman seule ne suffit pas. L’installation des dépendances utilise pacman et les dépôts configurés de la distribution. Cette détection ne garantit pas que chaque distribution dérivée et ses versions de paquets ont été testées.

Les liens actifs pointent vers le dépôt : modifier leur contenu dans un éditeur modifie donc les fichiers du dépôt. Ne pas déplacer ni supprimer le clone tant que ses configurations sont actives.

Dans GTK, l’aperçu d’activation regroupe les fichiers par configuration et présente l’action prévue, la source et la destination. Les filtres affichent tous les fichiers, les nouveaux liens, les liens déjà actifs ou les conflits à sauvegarder. Le résumé conserve les totaux de l’opération complète : fichiers, liens à créer et sauvegardes prévues. **Filtrer ne modifie pas la sélection à activer** ; changer de filtre retire l’accord coché, qu’il faut redonner après examen. Les aperçus de clonage et d’annulation conservent leur présentation textuelle.

Le tableau utilise une liste GTK qui réutilise ses cellules d’affichage, avec une colonne Configuration et des colonnes redimensionnables. Les lignes restent regroupées par configuration et triées par destination. Ce changement vise à éviter la création de milliers de widgets lors de l’ouverture ou du filtrage ; sa réactivité native reste à valider.

Le regroupement, le tri et le filtrage sont préparés en arrière-plan. Si plusieurs filtres sont demandés rapidement, seule la dernière demande en attente est conservée. GTK charge ensuite les données par lots de 200 lignes, avec un message de progression. L’accord et l’application restent désactivés jusqu’à la fin du chargement ; un changement de champ ou de filtre rend les anciens résultats et leurs lots inapplicables. Aucun gain de performance mesuré n’est encore revendiqué.

Dans **État actuel**, cliquez sur **Actualiser l’état** pour obtenir une observation datée en lecture seule. La commande `etat` fournit le même rapport en JSON, sans dépendre de GTK ou de Stow. Les sources absentes ou redirigées sont signalées séparément ; une erreur d’accès reste un état indisponible. Le rapport n’effectue aucune réparation et ne compare pas le contenu des fichiers.

Cette observation concerne les liens préexistants connus des aperçus et les interventions encore journalisées des déploiements non annulés. Elle exclut les opérations déjà restaurées ou jamais tentées et n’inventorie pas les liens sans journal, notamment une activation entièrement préexistante qui n’a créé aucun journal. Un même chemin peut figurer dans plusieurs déploiements : les compteurs portent sur les observations par journal, sans désigner un propriétaire unique. L’état peut changer pendant ou après l’analyse ; actualisez à nouveau au besoin. Une commande `etat` réussie signifie que le rapport a été produit, pas que tous les liens sont corrects.

Dans **Dépôt**, **Consulter l’état Git local** affiche une observation datée du dossier choisi. La commande `etat-git CHEMIN` fournit le même résultat en JSON. Les modifications préparées dans l’index sont distinguées de celles du dossier de travail ; un dépôt sans commit ou en révision détachée est identifié. Les noms de fichiers contenant des caractères de contrôle sont affichés avec échappement ; les octets non UTF-8 sont représentés par des séquences échappées.

La consultation Git ne lance ni `fetch`, ni `pull`, ni sous-module et ne vérifie pas le serveur distant. Elle désactive les verrous optionnels de l’index, les hooks, le moniteur de fichiers et les filtres externes de comparaison. Si de tels filtres sont configurés, le rapport le signale : les différences peuvent varier par rapport à Git utilisé avec ces filtres. Les fichiers ignorés et les changements internes aux sous-modules sont exclus. Choisir un sous-dossier au lieu de la racine du dépôt est refusé. Le rappel sur le risque de déplacer le dépôt est conditionnel : cette consultation ne compte pas les liens actifs. Le rapport est une observation ponctuelle, sans garantie d’instantané atomique.

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

Dans GTK, ouvrez **Sauvegardes et annulation**, puis **Actualiser l’historique**. Les déploiements sont présentés du plus récent au plus ancien avec leur date UTC, leur dépôt, leurs configurations, leur cible et leur état enregistré. Sélectionnez une ligne, puis **Préparer l’annulation** pour examiner les changements avant de donner votre accord dans l’aperçu. La saisie manuelle d’un identifiant reste disponible. Les déploiements annulés et les journaux illisibles restent visibles, mais leur bouton d’annulation est désactivé. L’état affiché provient du journal ; la possibilité réelle d’annuler est vérifiée au moment de préparer l’aperçu.

Les journaux et sauvegardes sont conservés dans `$XDG_STATE_HOME/dotfilepilot`, ou `~/.local/state/dotfilepilot`. Le dossier doit être privé (`0700`) ; les journaux sont écrits en `0600`. Les fichiers et liens remplacés sont déplacés dans un dossier daté avant Stow. Une annulation conserve les sauvegardes.

Avant le premier déplacement, l’activation vérifie que tous les conflits à sauvegarder résident sur le même système de fichiers que le dossier d’état. Sinon, elle refuse l’intervention : les sauvegardes par déplacement entre systèmes de fichiers ne sont pas prises en charge. L’annulation vérifie aussi la structure et la version du journal ; un journal illisible ou incomplet bloque la restauration sans modifier les configurations. Les anciens journaux sans numéro de version restent acceptés si leur structure est valide.

Une sauvegarde présente est contrôlée même si le fichier ou le lien original est déjà revenu en place. Une sauvegarde altérée bloque l’annulation. Après une interruption entre restauration et écriture du journal, une destination qui correspond déjà à l’original est conservée et son étape peut être enregistrée sans la recopier ni recréer son lien. Ces corrections sont codées ; leurs nouveaux tests de régression restent à exécuter.

Si Stow échoue, le journal reste dans l’état `interrompu`. Consulter `historique`, examiner `annuler IDENTIFIANT`, puis demander l’annulation. Aucun retour arrière silencieux n’est effectué. Les copies sensibles restent locales : ne pas les ajouter à Git. Cette reprise est testée pour les erreurs simulées ; elle ne constitue pas une garantie contre toute panne disque ou coupure d’alimentation.

## Vérification

```sh
make test
make check
# Sur une machine de test avec Stow déjà installé, données temporaires uniquement :
DOTFILEPILOT_TEST_STOW=1 make test
```

Voir le [bilan de validation et la recette Arch et dérivées](docs/validation.md), ainsi que le [cahier des charges et la suite du projet](docs/conception.md).

## Paquets GitHub

Comme Sambapilot, le workflow GitHub Actions prépare les tests Python, GTK4 et Stow, puis construit les archives Python et un paquet Arch `.pkg.tar.zst`. Les paquets vérifiés seront téléchargeables dans les artefacts de chaque exécution réussie, conservés 30 jours. Le paquet Arch déclare les dépendances et fournit le lanceur graphique.

Le [guide de distribution](docs/distribution.md) décrit le téléchargement et l’installation sur Arch Linux et ses dérivées. La chaîne est configurée localement ; aucune exécution GitHub ni construction Arch n’a encore été vérifiée.

L’[icône Dossier lié](docs/icone.md) est préparée en SVG et PNG, embarquée avec GTK et déclarée dans le lanceur et le paquet Arch. Son rendu natif et son association dans le menu des applications restent à valider.

Les commandes retournent `0` en cas de succès ou d’annulation volontaire, `2` pour une erreur et `3` si GTK est indisponible. `--version` affiche la version de développement.
