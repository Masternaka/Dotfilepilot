# Guide pour les assistants IA — Dotfilepilot

## Objectif et périmètre

Dotfilepilot est un gestionnaire de fichiers de configuration pour **Omarchy / Arch Linux**, inspiré de Sambapilot. Le terminal et l’interface native **GTK4** partagent le même moteur Python. Conserver Python 3.9 ou ultérieur et un moteur sans dépendance Python externe à l’exécution ; GTK et PyGObject sont facultatifs pour le terminal.

Le code permet de préparer puis de demander explicitement le clonage d’un dépôt HTTPS, l’installation des composants nécessaires, le déploiement Stow avec sauvegardes et l’annulation d’un déploiement. Contrairement au socle descriptif de Sambapilot, Dotfilepilot contient des fonctions qui peuvent réellement modifier des fichiers : ne jamais les lancer comme de simples diagnostics.

La cible actuelle est le dossier personnel. Les configurations système, les dépôts privés, les règles Stow personnalisées, les mises à jour Git et l’installation des applications configurées ne doivent pas être présentés comme pris en charge sans implémentation et validation correspondantes. Lire le [README](README.md) et la [conception](docs/conception.md) avant d’étendre ce périmètre.

## Autorisation et protection de l’ordinateur

**Ne rien installer ni appliquer sur l’ordinateur de l’utilisateur sans son autorisation explicite pour l’intervention concernée.**

- Une demande de développement autorise les modifications nécessaires dans ce dépôt, les lectures utiles et les vérifications isolées sur des données fictives. Elle n’autorise pas l’activation des configurations sur la machine.
- Avant toute installation, mise à jour, suppression de logiciel ou modification de configuration réelle, présenter l’action concrète, son périmètre et ses effets, puis obtenir l’autorisation correspondante. Réutiliser une autorisation déjà donnée pour ce même périmètre ; ne pas la redemander inutilement.
- Ne pas lancer Stow vers le dossier personnel réel, modifier les dotfiles actifs, appliquer une restauration réelle ni exécuter les scripts du dépôt de dotfiles pour tester l’application.
- Si un outil de vérification manque, signaler la limite. Ne pas installer GTK, PyGObject, Stow, un module de construction ou un gestionnaire de paquets pour débloquer un contrôle sans autorisation.
- Les tests peuvent créer et nettoyer leurs propres dossiers temporaires avec des données fictives ; ils ne doivent pas écrire dans les configurations ni les sauvegardes personnelles.
- Ne pas lancer l’application entière avec `sudo`. Le développement de son parcours d’installation via `sudo` et pacman reste autorisé lorsqu’il fait partie de la demande ; son exécution locale est une intervention distincte.
- Les installations prévues par la CI s’effectuent dans les runners et conteneurs GitHub jetables. Ne pas reprendre leurs commandes d’installation sur la machine de développement.

La confirmation demandée par l’application protège son utilisateur lors d’une intervention. Elle ne remplace pas l’autorisation donnée à l’assistant pour exécuter cette intervention.

## Démarrage d’une session

1. Lire ce fichier, le [README](README.md) et les documents utiles dans `docs/`.
2. Examiner `git status --short` et les différences concernées avant de modifier des fichiers.
3. Vérifier le comportement actuel dans le code ; les résumés de sessions et les projets voisins servent de contexte, sans remplacer cette vérification.
4. Réaliser la demande dans son périmètre, en conservant les parcours déjà acceptés. Une demande de maquette ou d’exploration visuelle seule n’autorise pas une refonte du code.

Préserver les modifications préexistantes, y compris les suppressions et réorganisations de l’utilisateur. Ne pas restaurer, écraser ou annuler un changement sans lien avec la demande.

## Organisation du dépôt

| Emplacement | Responsabilité |
| --- | --- |
| `dotfilepilot/system.py` | Diagnostic, identification Arch, dépendances et clonage HTTPS. |
| `dotfilepilot/deployments.py` | Inventaire, aperçus Stow, sauvegardes, journal, verrou et annulation. |
| `dotfilepilot/cli.py` | Commandes terminal et confirmation d’application. |
| `dotfilepilot/gui.py`, `dotfilepilot/gtk_app.py` | Chargement GTK à la demande et interface graphique. |
| `tests/` | Tests ordinaires et intégrations natives facultatives. |
| `scripts/` | Vérifications, bilans de tests et préparation des distributions. |
| `.github/workflows/ci.yml` | Tests Python et natifs, archives Python puis paquet Arch. |
| `packaging/arch/` | Modèle PKGBUILD et lanceur graphique. |
| `docs/` | Documentation française, conception, validation et distribution. |

Conserver les points d’entrée à la racine : `README.md`, `AGENTS.md`, `Makefile`, `pyproject.toml` et `MANIFEST.in`. Éviter les documents en double, les copies du code de projets voisins et les dossiers vides pour des fonctions futures. Ne supprimer que les artefacts dont l’inutilité est vérifiée ; préserver les tests, les entrées de conditionnement, les données et les sauvegardes.

## Conventions de développement

- Réponses, documentation, textes d’interface et messages de commit en français. Employer des noms de code cohérents avec les modules existants.
- Réutiliser les validations du moteur dans le terminal et GTK. Garder `gi` chargé à la demande pour que le terminal fonctionne sans GTK.
- Exécuter les opérations lentes hors du fil d’interface et invalider les résultats obsolètes. Ne pas appliquer une opération à partir d’une sélection ou d’une confirmation périmée.
- Conserver les appels de programmes sous forme de listes d’arguments avec `shell=False`, des délais et des erreurs explicites. Ne pas interpoler des chemins ou des URL dans un shell.
- Distinguer un outil absent d’une sonde en échec ou d’un état inconnu. Une erreur pacman ne prouve pas qu’un paquet manque.
- Conserver le clonage sans exécution des hooks, des scripts du dépôt ou des sous-modules. Ne pas ajouter de `pull`, de push ou de mise à jour automatique implicite : un changement du clone affecte immédiatement les configurations liées.
- Ne pas stocker de secrets, jetons GitHub, mots de passe, clés privées, configurations personnelles ou sauvegardes réelles dans le dépôt, les fixtures ou les journaux de CI.
- Faire des changements ciblés. Ajouter des tests pertinents pour les comportements et garanties modifiés ; une correction documentaire seule ne nécessite pas de nouveaux tests applicatifs.

## Garanties des déploiements et annulations

Préserver le parcours **analyse → aperçu → confirmation → revalidation → sauvegarde → application → vérification**.

- Sans `--appliquer`, les commandes d’intervention restent des aperçus. Dans GTK, l’application exige l’aperçu et l’accord explicite ; tout changement de champ ou de sélection invalide cet accord.
- Présenter les sources, destinations, liens déjà actifs et conflits avant intervention. Ne jamais adopter ou écraser silencieusement les fichiers existants.
- Garder le dépôt et la cible Stow explicites, utiliser `--no-folding` et ne pas ajouter `--adopt` au déploiement réel.
- Respecter les refus actuels sur les règles Stow implicites, les sources symboliques ou spéciales, les parents redirigés, les chemins hors périmètre et les cibles situées dans le dépôt. Étendre un cas refusé exige une analyse et des tests adaptés.
- Revalider les sources et destinations avant application ; refuser un aperçu devenu obsolète.
- Sauvegarder les fichiers et liens en conflit avant Stow, conserver leurs permissions et leur nature, protéger le dossier d’état et journaliser les étapes. Conserver le verrou empêchant les interventions concurrentes de Dotfilepilot.
- L’annulation retire uniquement les liens appartenant au déploiement concerné. Préserver les liens corrects préexistants, les modifications externes et les sauvegardes. Si l’état ne permet plus une restauration sûre, bloquer et expliquer.
- En cas d’échec, indiquer ce qui a changé, l’emplacement du journal et la procédure de reprise. Ne pas promettre une transaction atomique ni une récupération garantie après toute panne.
- Séparer les besoins de l’outil (`git`, Stow, GTK…) de l’installation facultative des applications configurées, et les fichiers du dossier personnel des modèles destinés à `/etc`.

Les journaux et sauvegardes durables restent hors du dépôt dans le dossier d’état utilisateur. Leur nettoyage, déplacement ou suppression ne fait pas partie d’une simple demande de rangement du code.

## Vérifications

Travailler depuis la racine, sans installation préalable du projet :

```sh
python3 -B -m dotfilepilot --help
make test
make check
```

`make test` utilise `scripts/run_tests.py`, qui contrôle aussi les tests ignorés. `make check` analyse la syntaxe Python, les cibles de liens Markdown prévues par le script et les espaces Git ; il ne prouve ni le rendu GTK ni une installation réussie.

Les tests natifs sont désactivés par défaut. Dans un environnement de test disposant déjà des composants, leur activation explicite peut utiliser :

```sh
DOTFILEPILOT_TEST_STOW=1 make test
python3 -B scripts/run_tests.py --require-native
```

La seconde commande exige GTK, un affichage utilisable et Stow ; aucun test natif ne doit être ignoré. Les fixtures doivent rester temporaires et fictives. Ne pas installer les composants ou configurer l’affichage de la machine pour faire passer cette commande sans autorisation.

Rapporter les résultats réellement observés en séparant les tests réussis, les tests ignorés, les contrôles statiques, les commandes simulées, le rendu GTK, les essais Stow réels, le clonage réseau, pacman et les essais sur Omarchy. Une image générée est une maquette, jamais une capture de l’application ni une validation visuelle native.

## GitHub et création des paquets

Conserver le fonctionnement décrit dans le [guide de distribution](docs/distribution.md) : vérifications Python et natives, puis archives Python contrôlées et paquet Arch construit avec `makepkg` sans privilèges dans le conteneur prévu.

- Déclarer les dépendances et le lanceur dans le conditionnement Arch ; ne pas déclencher de clonage ou d’activation de dotfiles lors de l’installation du paquet.
- Garder cohérentes les versions de `pyproject.toml` et de `dotfilepilot/__init__.py`. Préserver les empreintes des archives, le lien à la révision source et le refus d’écraser un dossier de préparation existant.
- Distinguer la validation du code, la construction d’une archive, son installation dans le conteneur et son utilisation sur Omarchy. Ne pas annoncer un paquet disponible sans avoir vérifié la réussite du workflow et ses artefacts.
- La chaîne conserve des artefacts de développement pendant 30 jours ; elle ne publie pas automatiquement de Release ni de dépôt pacman. Ne pas ajouter de signature, de canal de publication, de clé ou de licence sans décision de l’utilisateur.
- Ne pas créer de commit, pousser, ouvrir ou fusionner une pull request, créer un tag ou une Release, ni publier un paquet sans demande explicite couvrant l’action et sa cible. Une demande de modification du workflow ne vaut pas demande de publication.

## Documentation et reprise

Maintenir la documentation en Markdown local, en français. Le [README](README.md) décrit ce qui est utilisable ; la [conception](docs/conception.md) distingue le code présent des propositions ; le [bilan de validation](docs/validation.md) consigne les résultats et limites ; le [guide de distribution](docs/distribution.md) explique les paquets. Ne pas copier ou synchroniser ces documents vers Notion sans demande.

Actualiser les documents concernés quand une fonction, une commande, une limite ou la distribution change. Pour un travail long ou interrompu, noter dans `docs/` l’état réel, les décisions, les validations effectuées, ce qui reste à faire, les autorisations encore nécessaires et la première action de reprise, sans dupliquer inutilement les documents existants.

Terminer par un compte rendu bref : changements réalisés, vérifications effectuées et limites restantes. Ne pas attribuer à une session un test, un push ou une installation dont elle n’a pas la preuve.
