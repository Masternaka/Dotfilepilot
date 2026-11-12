# Validation et reprise

## Relecture de stabilisation — 12 novembre 2026

Relecture du moteur d’annulation, de la préparation différée des aperçus, des tests associés et de l’intégration de l’icône. Aucun nouveau blocage identifié dans ces passages par cette lecture ; aucune validation d’exécution n’en découle.

| Point relu | Constat dans le code | Validation restante |
| --- | --- | --- |
| Annulation | Une destination déjà restaurée ne saute plus le contrôle d’une sauvegarde présente ; la reprise évite de réécrire l’original. | Exécuter les régressions d’intégrité et d’interruption, puis la recette Stow. |
| Préparation et filtres | Les données sont préparées hors du fil GTK ; les générations sont revérifiées avant livraison et avant chaque lot. L’accord reste désactivé jusqu’au dernier lot courant. | Vérifier les vrais threads, les changements rapides de champs et de filtres, et les erreurs. |
| Modèle GTK | Les cellules sont réutilisées et les objets de lignes sont créés par lots de 200 ; les données restent conservées pour toutes les lignes affichées. | Mesurer temps, mémoire et défilement à 1 000 et 10 000 fichiers. |
| Icône | Même nom dans GTK et le lanceur ; assets déclarés dans le wheel, les sources et la recette Arch. | Construire les paquets, contrôler leur contenu et vérifier le rendu et l’association au bureau. |

Les scénarios GTK de préparation différée utilisent un ordonnanceur simulé : même exécutés avec GTK, ils ne démontrent pas à eux seuls le comportement des threads réels. Les contrôles de présence des icônes ne démontrent pas leur lisibilité. La recette ci-dessous complète ces limites sans les confondre avec les tests automatiques.

Cette session modifie uniquement ce document. Aucun test, contrôle Python, application, construction, installation ou workflow lancé. Aucune configuration personnelle modifiée, aucun commit ni push. Les résultats historiques ci-dessous concernent des états antérieurs du code.

## Icône Dossier lié — 12 novembre 2026

L’utilisateur a retenu la proposition 1. Son image est conservée dans les sources, avec neuf tailles PNG transparentes, un redessin SVG couleur simplifié et une variante symbolique. Les PNG proviennent directement du concept retenu : l’export SVG vers PNG par `sips` a échoué. Les métadonnées des PNG 16, 512 et 1024 ont été inspectées avec l’outil déjà présent ; leurs dimensions sont correctes et le canal alpha est présent. Le PNG a été observé comme image, sans lancement de l’application.

Le code GTK recherche ses assets embarqués et utilise le même nom que le lanceur : `io.github.dotfilepilot.App`. La recette Arch, le nom du lanceur installé, les manifests Python et les contrôles de distribution sont adaptés. Un test de métadonnées des assets a été ajouté et le test GTK de navigation est complété pour vérifier le nom de l’icône et sa découverte par le thème.

**Aucun test applicatif, contrôle Python, construction ou installation de paquet effectué.** Les commandes locales ont servi uniquement à lire les fichiers et à préparer ou inspecter les images avec les outils existants. Aucun logiciel installé, aucune configuration personnelle ou icône du bureau actif modifiée. Aucun commit ni push.

Première reprise dans un environnement autorisé : exécuter les vérifications ordinaires et natives, construire les distributions et le paquet Arch, puis vérifier le SVG, la lisibilité des petites tailles, le chargement depuis les sources et le wheel, et l’association au menu et à la fenêtre après installation. La [fiche de l’icône](icone.md) détaille les fichiers et leur provenance.

## Préparation de l’aperçu hors du fil GTK — 12 novembre 2026

Le regroupement, le tri et le filtrage du tableau d’activation sont maintenant préparés en arrière-plan, sous forme de données Python sans objets GTK. Une seule préparation travaille à la fois ; seule la dernière demande de filtre en attente est conservée. La livraison au modèle GTK se fait par lots de 200 lignes, avec progression. L’accord et l’application sont désactivés pendant la préparation et le chargement. Les générations de champs et de demandes sont vérifiées à la livraison puis avant chaque lot pour empêcher un résultat obsolète de réactiver une intervention. Les erreurs de préparation ou de création des lignes laissent l’application désactivée.

Les tests GTK existants du tableau ont été adaptés à cette préparation différée avec un ordonnanceur contrôlé, sans attente ni threads réels dans ces scénarios. Six tests GTK supplémentaires couvrent les filtres successifs, le refus d’appliquer pendant la préparation, l’arrêt des anciens lots, la modification des champs, le remplacement par un aperçu de clonage et les erreurs de préparation ou de chargement. Un test sans GTK a été ajouté pour les données de lignes triées et l’absence de modification du plan.

**Aucun test, contrôle Python, application ou installation lancé sur le Mac pour ces changements.** Les fichiers et le diff ont uniquement été relus. Les résultats historiques ci-dessous ne valident pas ce nouveau code. Aucun changement de configuration personnelle, commit ou push.

Première validation dans un environnement autorisé : exécuter les suites ordinaires et natives, puis mesurer l’ouverture, le défilement et le filtrage d’aperçus de 1 000 et 10 000 fichiers. Vérifier les changements rapides de filtre et de champs, y compris pendant le chargement des lots, et le maintien de l’application du plan complet après un nouvel accord. Aucun gain chiffré n’est revendiqué. Les données restent recalculées par filtre exécuté, sans cache, et le modèle garde toutes les lignes affichées.

## Corrections après revue en lecture seule — 12 novembre 2026

Trois corrections ont été apportées au code du dépôt à la demande de l’utilisateur :

- L’aperçu d’annulation ne saute plus le contrôle d’une sauvegarde lorsque la destination correspond déjà à son état original. Une sauvegarde présente mais altérée reste bloquante.
- La reprise reconnaît une destination déjà restaurée avant la dernière écriture du journal. Elle conserve le fichier ou le lien en place et enregistre l’étape sans le recopier ni recréer un lien existant.
- Le tableau d’activation utilise `Gtk.ColumnView` avec un modèle et des cellules réutilisables. Il ne construit plus trois labels pour chaque fichier ni un texte complet d’activation masqué. Le filtre conserve les totaux globaux et retire toujours l’accord coché.

Quatre tests de régression du moteur ont été ajoutés pour les sauvegardes altérées devant une destination déjà restaurée, et pour les interruptions après restauration d’un fichier ou d’un lien symbolique mais avant écriture du journal. Deux tests GTK ont été ajoutés pour un modèle de 10 000 fichiers, le filtrage et la réaffectation d’une cellule à une nouvelle ligne.

**Aucun test, contrôle Python ou lancement de l’application effectué pour ces corrections**, conformément à la demande de ne rien installer ou exécuter pour tester sur le Mac. La relecture des fichiers et du diff est la seule vérification réalisée ; les résultats des sections antérieures ne valident pas ces nouveaux changements. Aucun composant installé, aucune configuration personnelle modifiée, aucun commit ni push du projet.

Première action de reprise dans un environnement de test autorisé : exécuter `make test` et `make check`, puis la suite native déjà prévue. Vérifier aussi une interruption entre restauration et enregistrement du journal, le maintien du refus devant une sauvegarde altérée et le défilement du tableau sur un grand aperçu. Aucun gain de temps ou de mémoire n’est revendiqué sans mesure native. Le modèle conserve toutes les lignes ; seules les cellules GTK sont réutilisées.

## Consultation Git locale — 12 novembre 2026

Le bouton **Consulter l’état Git local** de la page Dépôt et la commande `etat-git CHEMIN` affichent branche, révision, changements indexés et changements du dossier de travail. Les dépôts sans commit et les révisions détachées sont distingués. Un sous-dossier est refusé pour ne pas consulter implicitement le dépôt parent. Aucun accès distant ni mise à jour automatique. Un rappel conditionnel explique le risque de casser les liens en déplaçant ou supprimant le dépôt.

`make test` : **88 tests découverts, 72 réussis et 16 ignorés** (1 Stow, 15 GTK). Onze nouveaux tests utilisent Git local déjà disponible et des dépôts temporaires fictifs, ainsi que des simulations ciblées d’erreurs. Ils couvrent les branches, la révision détachée, les fichiers modifiés/ajoutés/supprimés/non suivis/ignorés, les noms atypiques, les erreurs de dossier, l’absence de réécriture de l’index et les erreurs Git. Des filtres externes et un moniteur de fichiers fictifs sont configurés pour vérifier qu’ils ne sont pas exécutés pendant la consultation. Les conflits et renommages du parseur sont vérifiés avec une réponse porcelain fictive ; aucun conflit réel n’est revendiqué. Les transports bloqués et les délais sont contrôlés par simulation. Deux nouveaux tests GTK couvrent l’affichage et le rejet d’un résultat devenu obsolète ; ils restent ignorés localement. `make check` réussit (22 fichiers Python, liens Markdown et espaces Git), ainsi que l’aide du terminal.

Les tests créent des commits uniquement dans leurs dépôts temporaires. Aucun commit ou push du projet, aucune installation, aucune consultation réseau ni modification de configuration personnelle. Le rendu GTK et les essais Arch/Omarchy restent à effectuer. La neutralisation des filtres peut modifier les différences affichées et est signalée dans le rapport. Le rapport exclut les sous-modules et ne garantit pas un instantané atomique en présence de changements simultanés. Première reprise : exécuter la suite native dans l’environnement équipé puis vérifier la consultation depuis la page Dépôt, avec changements locaux et changement de chemin pendant l’analyse.

## État actuel en lecture seule — 12 novembre 2026

Nouvelle page GTK **État actuel**, avec actualisation explicite en arrière-plan, et commande terminal `etat` partageant le même moteur sans dépendance à GTK ou Stow. Le rapport daté examine les liens connus des journaux non annulés et distingue les liens corrects, cassés, remplacés, absents ou indisponibles. Les liens préexistants au déploiement sont distingués des interventions journalisées. Les sources absentes ou redirigées et les journaux invalides restent signalés. Les compteurs portent sur les observations par journal ; un même chemin peut apparaître plusieurs fois. Aucun propriétaire unique n’est déduit.

`make test` : **75 tests découverts, 61 réussis et 14 ignorés** (1 Stow, 13 GTK). Treize nouveaux tests ordinaires couvrent les observations sur fixtures temporaires avec Stow simulé, les sources disparues, les remplacements, les redirections, les accès refusés simulés, les boucles symboliques, les annulations, les interruptions, les journaux invalides et superposés, la présentation et la commande terminal. Les tests vérifient aussi l’absence de création du dossier d’état et de modification des journaux observés. Deux nouveaux tests GTK couvrent l’actualisation, l’invalidation de l’accord et le rejet d’un résultat obsolète ; ils restent ignorés localement. `make check` réussit (20 fichiers Python, liens Markdown et espaces Git), ainsi que l’aide du terminal.

Aucune observation des configurations personnelles réalisée. Aucun logiciel installé, aucune configuration réelle activée, aucun commit ni push. Rendu GTK, parcours clavier, comportement sur gros historiques et essais Stow/Omarchy réels restent à valider plus tard. Première reprise : exécuter la suite native dans un environnement équipé, puis vérifier l’actualisation avant et après un déploiement fictif, son annulation et le déplacement de son dépôt. Le rapport ne contrôle pas le contenu des configurations et ne constitue pas un instantané atomique.

## Tableau d’aperçu d’activation — 12 novembre 2026

L’aperçu GTK d’activation regroupe les fichiers par configuration et affiche l’action, la source et la destination dans un tableau défilant. Les filtres proposent tous les fichiers, les nouveaux liens, les liens déjà actifs et les conflits à sauvegarder. Le résumé garde les totaux complets ainsi que le nombre de liens à créer et de sauvegardes prévues ; un compteur distingue les lignes visibles. Un filtre sans résultat affiche un message explicite. Changer de filtre retire l’accord coché sans modifier le plan complet à appliquer. Le clonage et l’annulation conservent leurs aperçus textuels.

`make test` : **60 tests découverts, 48 réussis et 12 ignorés** (1 Stow, 11 GTK). Cinq nouveaux tests sans GTK vérifient le regroupement exact des configurations, les chemins avec espaces et accents, les filtres, les totaux complets et l’absence de modification du plan. Trois nouveaux tests GTK couvrent le résumé sous filtre, l’invalidation de l’accord, l’application du plan complet après confirmation, les filtres vides et les autres types d’aperçu ; ils restent ignorés localement. `make check` réussit (18 fichiers Python, liens Markdown et espaces Git), ainsi que l’aide du terminal.

Aucun rendu GTK, essai Stow réel, installation ou changement de configuration personnelle effectué. Le tableau et les interactions restent à valider dans l’environnement natif prévu, notamment les chemins longs, les grands volumes, la navigation au clavier et le passage entre aperçu, intervention et résultat. La vue de l’état actuel est décrite ci-dessus. Aucun commit ni push effectué pour ces changements.

## Historique sélectionnable — 12 novembre 2026

L’interface GTK contient une liste sélectionnable, du plus récent au plus ancien, avec date UTC, dépôt, configurations, cible et état enregistré. Une sélection remplit l’identifiant et invalide l’accord précédent. Le bouton prépare uniquement l’aperçu d’annulation ; l’intervention exige toujours un nouvel accord et une revalidation. La saisie manuelle reste possible. Les entrées annulées ou illisibles restent visibles sans permettre l’annulation depuis leur bouton. La lecture détaillée ne sonde pas les destinations et ne crée pas de dossier d’état ; un journal endommagé ne masque pas les autres. La sortie terminal de `historique` reste inchangée.

`make test` : **52 tests découverts, 43 réussis et 9 ignorés** (1 Stow, 8 GTK). Cinq nouveaux tests ordinaires vérifient les résumés, les états actif et annulé, l’isolation des journaux endommagés, l’absence d’inspection des cibles et les lectures sans création du dossier d’état. Trois nouveaux tests GTK couvrent la sélection, la préparation sans application, l’invalidation de l’accord, la saisie manuelle et les entrées indisponibles ; ils restent ignorés localement. `make check` et l’aide du terminal réussissent.

Aucune installation, intervention sur les configurations personnelles ou publication effectuée. Le rendu et les interactions GTK restent à valider ultérieurement avec la suite native, notamment la navigation au clavier, les listes longues et la sélection avant annulation. La vue de l’état actuel et le tableau d’aperçu sont décrits ci-dessus.

## Renforcement du 12 novembre 2026

Corrections locales du moteur et de GTK :

- Le résultat et l’erreur d’une intervention restent affichés après modification d’un champ pendant son exécution. Les analyses obsolètes restent écartées, et l’accord est toujours invalidé.
- L’activation refuse les conflits situés sur un système de fichiers différent du dossier d’état avant tout déplacement ou création de journal de déploiement. Le dossier d’état et son verrou peuvent être créés lors de cette vérification.
- L’annulation valide les champs utilisés pour la reprise, les empreintes, les chemins, les doublons et la version du journal. Les journaux illisibles ou incomplets produisent une erreur explicite ; les anciens journaux sans version restent compatibles. Cette validation ne garantit pas l’authenticité d’un journal altéré.

`make test` : 44 tests découverts, **38 réussis et 6 ignorés** (1 Stow, 5 GTK). Les nouveaux tests ordinaires couvrent le refus de sauvegardes entre systèmes de fichiers simulés, les journaux endommagés et la restauration depuis un ancien journal. Trois tests GTK supplémentaires couvrent le résultat, l’erreur et l’analyse obsolète après modification d’un champ ; ils sont ignorés localement et restent à exécuter dans l’environnement natif prévu. `make check` et l’aide du terminal réussissent.

Aucune installation ni configuration personnelle modifiée. Aucun essai réel entre systèmes de fichiers, rendu GTK, essai Stow réel ou workflow GitHub effectué dans cette session. Prochaine validation : exécuter la suite native sur une machine de test équipée, puis suivre la recette Omarchy ci-dessous. La vue de l’état actuel, l’historique sélectionnable et le tableau d’aperçu sont décrits ci-dessus.

## État au 9 novembre 2026

Développement et tests effectués sur macOS avec Python 3.9.6. Aucun logiciel installé, aucun clone réseau réalisé, aucune configuration personnelle activée ou modifiée.

`make test` : 37 tests découverts, 34 réussis et 3 intégrations natives ignorées (1 Stow, 2 GTK). Les tests vérifient notamment les sauvegardes de fichiers et de liens cassés, les permissions restaurées, l’annulation après erreur simulée, les aperçus obsolètes, les fichiers modifiés après déploiement, les sources spéciales, les chemins redirigés, plusieurs configurations avec des espaces dans le chemin du dépôt et la préparation de la recette Arch sans écrasement.

La chaîne GitHub de [distribution](distribution.md) ajoute des bilans JSON, des tests natifs obligatoires, des contrôles d’archives et des tests après installation dans les environnements temporaires du runner. Le YAML est analysé localement. Le module Python `build` n’est pas installé ici : les archives réelles et le paquet Arch n’ont pas été construits sur ce Mac.

Stow n’est pas installé dans cet environnement. Le simulateur des tests vérifie le moteur de journalisation ; il ne prouve pas la compatibilité des commandes et règles avec GNU Stow. L’interface GTK est contrôlée uniquement par sa syntaxe Python. Aucun rendu graphique n’a été observé.

## Correction de l’échec Arch signalé le 9 novembre 2026

Le journal GitHub fourni par l’utilisateur montre une construction du wheel réussie, puis un échec du test Stow réel pendant `makepkg check()` : `stow: No packages to stow or unstow`.

La commande produite plaçait `--` entre `--stow` et les noms des configurations. Stow récupère ces noms avec le callback des arguments non optionnels de `Getopt::Long` : le séparateur arrête l’analyse avant ce callback. La commande a été corrigée en retirant ce séparateur ; les noms restent validés par le moteur avant l’appel. Le simulateur a été corrigé pour ne plus masquer ce comportement.

Une reproduction locale avec le module Perl `Getopt::Long`, déjà disponible, confirme que `--stow -- zsh` laisse la liste des paquets vide alors que `--stow zsh` transmet `zsh`. Référence : [analyseur de GNU Stow](https://github.com/aspiers/stow/blob/master/bin/stow.in). Ce contrôle n’est pas une exécution de Stow : la reconstruction complète du paquet Arch reste à vérifier lors d’une prochaine exécution GitHub.

## Recette à effectuer sur Arch / Omarchy

**Procédure future, non exécutée sur le Mac.** Utiliser un compte de test sur Arch / Omarchy ou une machine virtuelle jetable, avec Python, Git, Stow, GTK4, PyGObject et un affichage déjà disponibles. Si un composant manque, arrêter et préparer séparément son installation après autorisation. Travailler depuis la racine du projet, sans `sudo` pour l’application. Aucun dossier personnel réel ne doit servir de cible.

### 1. Vérifications automatiques

```sh
make check
make test
python3 -B scripts/run_tests.py --require-native
```

Résultat attendu : suites réussies ; aucun test natif ignoré pour la dernière commande. Relever la révision utilisée, les nombres de tests et les erreurs éventuelles. Ces résultats ne remplacent pas les essais GTK manuels ci-dessous.

### 2. Préparer une cible et un état isolés

Les commandes suivantes sont à saisir uniquement dans l’environnement Linux de test autorisé. Elles créent des fichiers fictifs sous `/tmp` ; la fonction `dp_recette` n’existe que dans le terminal courant et ne modifie aucun fichier de configuration du shell.

```sh
DOTFILEPILOT_RECETTE=$(mktemp -d /tmp/dotfilepilot-recette.XXXXXX)
mkdir -p "$DOTFILEPILOT_RECETTE/depot/exemple/.config/dotfilepilot-exemple"
mkdir -p "$DOTFILEPILOT_RECETTE/cible/.config/dotfilepilot-exemple"
printf '%s\n' 'source fictive' > "$DOTFILEPILOT_RECETTE/depot/exemple/.config/dotfilepilot-exemple/settings"
printf '%s\n' 'original fictif' > "$DOTFILEPILOT_RECETTE/cible/.config/dotfilepilot-exemple/settings"
chmod 640 "$DOTFILEPILOT_RECETTE/cible/.config/dotfilepilot-exemple/settings"

dp_recette() {
    XDG_STATE_HOME="$DOTFILEPILOT_RECETTE/etat" python3 -B -m dotfilepilot "$@"
}
```

Les règles Stow personnelles implicites restent bloquantes : si l’analyse en trouve, ne pas les déplacer ou les modifier pour contourner le refus ; utiliser un compte de test vierge. Conserver le chemin temporaire et ses journaux jusqu’à la fin de la recette ; aucun nettoyage automatique n’est prévu ici.

### 3. Activation et annulation réelles, sur les fixtures seulement

```sh
dp_recette inventaire "$DOTFILEPILOT_RECETTE/depot"
dp_recette activer "$DOTFILEPILOT_RECETTE/depot" exemple --cible "$DOTFILEPILOT_RECETTE/cible"
dp_recette activer "$DOTFILEPILOT_RECETTE/depot" exemple --cible "$DOTFILEPILOT_RECETTE/cible" --appliquer
dp_recette historique
dp_recette etat
```

Avant de taper `OUI`, vérifier dans l’aperçu que dépôt et cible sont sous le dossier temporaire. Résultat attendu : l’original fictif est sauvegardé sous `etat/dotfilepilot`, la destination devient un lien vers la source fictive et `etat` le signale comme correct. La première commande d’activation, sans `--appliquer`, ne doit déplacer aucun fichier.

Copier l’identifiant produit à la place de `IDENTIFIANT` :

```sh
dp_recette annuler IDENTIFIANT
dp_recette annuler IDENTIFIANT --appliquer
dp_recette etat
```

Résultat attendu : destination redevenue un fichier contenant `original fictif`, permissions `0640`, sauvegarde conservée et journal marqué `annule`. Les tests de régression couvrent séparément l’interruption simulée après restauration mais avant sauvegarde du journal, ainsi que le refus devant une sauvegarde altérée. Leur réussite ne garantit pas la reprise après toute panne matérielle.

### 4. Vérifier GTK et ses tâches réelles

Fermer toute instance de Dotfilepilot déjà ouverte dans le compte de test avant cette étape : une application GTK déjà enregistrée pourrait recevoir la demande d’ouverture avec son ancien dossier d’état.

```sh
dp_recette gui
```

Dans **Dépôt**, choisir le dépôt fictif ; dans **Configurations**, remplacer impérativement la cible proposée par le dossier `cible` temporaire avant de préparer une activation. Dans **Sauvegardes et annulation**, vérifier la sélection et la saisie manuelle de l’identifiant, puis l’actualisation de **État actuel**. L’état doit rester dans le dossier temporaire.

Créer ensuite un paquet fictif `volume` contenant 1 000 puis 10 000 dotfiles sous ce même dépôt, sans dépasser la limite de 10 000 fichiers sélectionnés. Préparer son activation sans l’appliquer et relever le temps d’ouverture, la mémoire et la fluidité du défilement. Vérifier les chemins longs et la navigation au clavier. Pendant la préparation et le chargement :

- Changer rapidement de filtre : seul le dernier doit être livré, avec les totaux complets ; l’accord doit être retiré et indisponible pendant le chargement.
- Changer le dépôt, la cible ou les configurations cochées : aucun ancien résultat ne doit réactiver l’application. Refaire un aperçu pour poursuivre.
- Depuis un aperçu courant, changer de filtre puis confirmer : le filtre limite seulement l’affichage ; toute intervention autorisée concerne le plan complet présenté dans les totaux.

### 5. Vérifier les refus et les consultations

Sur les fixtures uniquement, remplacer un lien déployé par un fichier différent : l’aperçu d’annulation doit refuser de l’écraser. Modifier une source ou une destination après un aperçu d’activation : l’intervention doit demander une nouvelle analyse. Préserver les journaux des refus.

Dans un dépôt Git fictif, consulter `etat-git` puis le bouton GTK correspondant : vérifier branche, révision et changements locaux, sans modification de l’index ni accès distant. Le clonage réseau et `dependances --appliquer` restent des essais distincts, à autoriser dans une machine virtuelle jetable ; ils ne sont pas nécessaires à cette recette courte.

### 6. Vérifier la distribution et l’icône séparément

Après autorisation de publication des sources et réussite du workflow sur cette même révision, examiner les bilans et les artefacts décrits dans le [guide de distribution](distribution.md). Une ancienne exécution ne valide pas les nouveaux changements.

Après installation du paquet dans le seul environnement de test autorisé, vérifier le lanceur `io.github.dotfilepilot.App.desktop`, l’icône du menu et l’association à la fenêtre sous le bureau cible. Comparer le rendu SVG et les PNG en petites tailles ; voir la [fiche de l’icône](icone.md). La présence des fichiers dans le paquet ne prouve pas leur rendu dans GTK ou le menu.

Pour chaque étape, consigner **réussi**, **échoué** ou **non effectué**, avec environnement, révision et preuve observée. Toutes les étapes de cette recette restent actuellement **non effectuées** dans cette session.

## Reprendre le travail

Les derniers correctifs d’annulation, la préparation différée de l’aperçu et l’icône restent sans nouvelle validation d’exécution. Sur le Mac, poursuivre seulement les lectures et les modifications de dépôt explicitement demandées ; aucune installation ni exécution de tests n’est autorisée actuellement. Pour valider, utiliser un environnement de test autorisé et commencer par l’étape 1 de la recette ci-dessus. Un commit/push et toute installation sur une cible restent soumis à une autorisation distincte. Vérifier ensuite une nouvelle exécution GitHub depuis la révision qui contient tous les fichiers ajoutés, y compris les assets non suivis. Les mises à jour Git restent à développer. Aucun commit, push, paquet publié ou installation n’a été effectué dans cette session.
