# Conception de Dotfilepilot

## Objectif retenu

Créer un gestionnaire de dotfiles pour Arch Linux et ses distributions dérivées, sur le modèle de Sambapilot : moteur Python commun, terminal autonome et interface GTK4. Le choix de la famille Arch a été confirmé ; le périmètre vise ses différentes distributions, sans dépendre d’un bureau particulier.

L’utilisateur doit pouvoir préparer sa machine, cloner son dépôt, choisir ses configurations, consulter les conflits, activer les liens et revenir à son état précédent pour les fichiers concernés.

Le moteur accepte Linux avec `ID=arch` ou `arch` comme élément de `ID_LIKE` dans `os-release`, sans liste de noms de distributions. Le fichier `/usr/lib/os-release` sert de repli uniquement si `/etc/os-release` est absent. Le contenu est analysé comme des valeurs déclaratives avec gestion des guillemets, sans exécution de shell. Une identité illisible, mal formée ou non reconnue ne permet pas d’intervention. La préparation des dépendances conserve pacman ; les noms et versions disponibles dans chaque distribution restent à valider sur leurs environnements réels.

## Architecture présente

- `system.py` : diagnostic, identification Arch, plan de dépendances, installation terminal et clonage HTTPS.
- `git_status.py` : consultation locale de la branche, de la révision et des changements du dépôt, partagée par `etat-git` et GTK.
- `deployments.py` : inventaire, analyse Stow isolée, empreintes des sources et destinations, sauvegardes, journal et annulation.
- `monitoring.py` : observation en lecture seule des liens connus des journaux, partagée par `etat` et GTK.
- `cli.py` : commandes et confirmation explicite.
- `gui.py` / `gtk_app.py` : chargement GTK facultatif, navigation et opérations en arrière-plan.
- `presentation.py` : regroupement, filtrage et comptage de l’aperçu d’activation, ainsi que présentation du rapport d’état, sans GTK ni accès aux fichiers.
- `tests/` : scénarios isolés avec fichiers temporaires, commandes simulées et intégration Stow facultative.
- `.github/workflows/ci.yml` et `packaging/arch/` : chaîne de tests, archives Python et paquet Arch, configurée mais encore à valider sur GitHub.

Le moteur n’exécute pas de shell. Le clonage désactive les hooks, les modèles Git, les configurations Git globales et les sous-modules. Cette première version ne gère ni authentification privée, ni secrets enregistrés, ni exécution des programmes du dépôt.

Stow est invoqué avec un dépôt et une cible explicites ainsi que `--no-folding`. Le premier calcul se fait dans un dossier temporaire vide ; les liens obtenus servent à l’aperçu réel. Les conflits sont sauvegardés avant l’application, sans utilisation de `--adopt`. Une annulation retire seulement les liens créés par le déploiement concerné et restaure ses sauvegardes. Les liens corrects qui existaient déjà ne lui appartiennent pas.

L’aperçu d’annulation vérifie une sauvegarde présente même si la destination correspond déjà à l’état original. Une destination déjà restaurée est reconnue par sa nature, son contenu et ses permissions pour un fichier, ou par le texte du lien pour un lien symbolique. La reprise enregistre alors l’étape sans réécrire cette destination. Cette reconnaissance vise notamment une interruption survenue après restauration mais avant mise à jour du journal ; elle ne remplace pas les contrôles d’intégrité des sauvegardes et les refus sur les modifications externes.

## Parcours graphique

1. **Accueil et dépendances** : consulter le diagnostic et la commande d’installation dans un terminal.
2. **Dépôt** : préparer un clonage, analyser un dossier existant ou consulter son état Git local en lecture seule.
3. **Configurations** : cocher les paquets et choisir la cible.
4. **Aperçu** : examiner le tableau d’activation regroupé par configuration (action, source, destination), filtrer par état, puis cocher l’autorisation et appliquer. Le résumé conserve les totaux complets même sous filtre.
5. **Sauvegardes et annulation** : actualiser la liste des déploiements (date UTC, dépôt, configurations, cible et état), sélectionner une ligne et préparer une restauration. La saisie manuelle d’un identifiant reste possible.
6. **État actuel** : demander une observation datée des liens journalisés, sans intervention. Le chargement se fait en arrière-plan et les résultats devenus obsolètes sont écartés.

Une modification des champs ou de la sélection invalide l’autorisation. Le moteur recalcule l’aperçu avant l’activation. Pendant une opération en cours, la fermeture de la fenêtre est bloquée pour ne pas interrompre volontairement une écriture.

Les résultats d’analyse devenus obsolètes sont écartés. Le résultat ou l’erreur d’une intervention reste affiché même si les champs ont changé pendant son exécution : ces changements n’annulent pas l’intervention en cours. L’accord reste invalidé ; toute nouvelle intervention exige un nouvel aperçu.

La lecture détaillée de l’historique s’effectue en arrière-plan sans inspecter les cibles ni créer de dossier d’état. Un journal invalide apparaît avec son erreur sans masquer les autres entrées. Sélectionner un autre déploiement ou actualiser la liste invalide l’accord précédent. L’état affiché est celui du journal ; les contrôles des fichiers réels restent effectués par l’aperçu d’annulation et sa revalidation. La commande terminal `historique` conserve sa liste d’identifiants.

Les filtres de l’aperçu d’activation modifient seulement les lignes affichées. Ils retirent l’accord coché sans modifier le plan ni l’action à confirmer ; l’application utilise toujours le plan complet et sa revalidation par le moteur. Un nouveau travail en arrière-plan masque le tableau précédent pour afficher sa progression, puis son résultat ou son erreur. Le clonage et l’annulation conservent leurs aperçus textuels.

Le tableau repose sur `Gtk.ColumnView`, un modèle `Gio.ListStore` et des fabriques de cellules réutilisables. Le modèle conserve les données de chaque ligne, tandis que GTK crée les cellules nécessaires à l’affichage. Les configurations occupent une colonne et restent contiguës après tri ; les colonnes sont redimensionnables. Un nouveau travail libère le modèle précédent. Le texte détaillé d’activation n’est plus construit dans une vue masquée.

`presentation.activation_table` prépare le regroupement, le tri, les compteurs et les lignes sous forme de données Python, hors du fil GTK et sans créer de GObject. Une seule préparation d’affichage travaille à la fois ; les changements rapides de filtre remplacent la demande en attente par la plus récente. Une génération de champs et un numéro de demande identifient les résultats encore valides.

La livraison revient au fil GTK, qui crée les objets de lignes par lots de 200 via la boucle GLib. Chaque lot vérifie encore sa validité avant d’ajouter des lignes. Un nouveau filtre vide le modèle et retire l’accord ; un changement de champ annule aussi l’action préparée. L’application ne redevient possible qu’après le dernier lot du résultat courant et exige un nouvel accord explicite. Les erreurs de préparation ou de chargement laissent l’intervention désactivée. Les aperçus textuels de clonage et d’annulation conservent leur parcours.

La préparation reste proportionnelle au nombre de fichiers et les données sont recalculées pour chaque filtre exécuté ; aucun cache de filtres n’est ajouté. Le modèle conserve toutes les lignes affichées. Aucune mesure de performance native n’est encore disponible.

## Observation de l’état présent

Le moteur lit les journaux valides non annulés. Il examine les liens déjà actifs dans leur aperçu et les interventions encore présentes dans `records`, en excluant les étapes déjà restaurées et les nouveaux liens jamais tentés. Il distingue liens corrects, cassés, remplacés, absents et chemins indisponibles ; les sources indisponibles ou redirigées sont signalées séparément. Un journal invalide n’empêche pas l’observation des autres. Les déploiements annulés sont comptés sans inspection de leurs cibles.

Les observations restent séparées par déploiement, y compris lorsqu’un chemin figure dans plusieurs journaux. Elles n’établissent ni un propriétaire unique, ni une création effective après une interruption. Aucun contenu de configuration n’est lu ou comparé, aucun programme externe n’est lancé, aucun verrou ou dossier d’état n’est créé. Le rapport ne constitue pas un instantané atomique : des fichiers peuvent changer pendant l’analyse. Les liens sans journal ne sont pas découverts. L’authenticité des journaux n’est pas garantie par leur validation de structure.

## Consultation Git locale

`etat-git` et le bouton de la page Dépôt utilisent le même moteur. Il refuse un dossier situé à l’intérieur d’un autre dépôt et lit la branche, l’identifiant du commit et les changements via le format Git porcelain v2 délimité par NUL. L’index et le dossier de travail sont distingués ; l’absence de commit et la révision détachée sont représentées explicitement. Le rapport exclut les fichiers ignorés et les sous-modules. Les renommages apparaissent comme suppressions et ajouts, sans calcul de similarité.

Les commandes utilisent des listes d’arguments et un délai de 30 secondes par appel. L’environnement Git hérité est nettoyé, les configurations globales et système sont ignorées, les transports sont interdits et les verrous optionnels désactivés. Les hooks et le moniteur de fichiers sont neutralisés. Les pilotes de filtres déclarés dans la configuration locale, y compris ses inclusions, sont repérés puis désactivés par options de commande pour la lecture de l’état. Leur présence est signalée, car cette neutralisation peut changer les différences affichées. Le moteur ne réécrit pas la configuration locale et n’effectue aucune mise à jour Git.

GTK lance la consultation en arrière-plan et écarte le résultat si les champs ont changé. Le rappel indique que déplacer ou supprimer le dépôt peut casser les liens qui y pointent ; aucun décompte de liens actifs n’est déduit de cet état Git. Plusieurs lectures successives ne constituent pas un instantané atomique du dépôt, notamment si ses fichiers ou sa configuration changent simultanément.

## Limites de la première version

Le code constitue une version de développement, pas une version prête pour les configurations personnelles. La validation native Stow, GTK, pacman, sudo et Git réseau reste à réaliser. Les protections visent les erreurs courantes et les changements entre aperçu et application ; elles ne garantissent pas une transaction atomique face à un autre programme qui modifie simultanément les mêmes chemins.

Le mode utilisateur vise le dossier personnel. Les modèles destinés à `/etc`, comme Samba et pacman, exigent un futur parcours séparé. Aucun privilège administrateur n’est utilisé pour Stow. Les répertoires vides créés par Stow ne sont pas supprimés lors de l’annulation.

## Évolution possible vers d’autres distributions Linux

**Proposition future, non implémentée.** La structure du projet constitue une base réutilisable pour prendre en charge d’autres familles Linux, mais leur compatibilité n’est pas acquise. Le périmètre actuel reste Arch Linux et ses distributions dérivées.

| Partie | Situation actuelle | Adaptation nécessaire |
| --- | --- | --- |
| Déploiement, sauvegardes et annulation | Moteur largement réutilisable sur Linux, fondé sur Python et GNU Stow. | Valider les chemins, permissions, conflits et reprises dans chaque environnement cible. |
| Terminal et interface GTK4 | Deux interfaces partageant le même moteur ; GTK reste facultatif pour le terminal. | Adapter les indications de préparation et valider les composants graphiques disponibles. |
| Détection et autorisation | Les interventions sont réservées à la famille Arch, identifiée par `os-release`. | Distinguer l’identité du système de ses capacités et des familles réellement prises en charge. |
| Installation des dépendances | Commandes pacman et noms de paquets propres à cette famille. | Prévoir des adaptateurs de gestionnaires de paquets et leurs correspondances de dépendances. |
| Distribution de l’application | Archives Python et recette de paquet Arch. | Préparer et valider le conditionnement et le lanceur adaptés aux nouvelles familles. |

Pour envisager Debian, Ubuntu, Linux Mint ou Fedora, séparer les particularités de distribution du moteur commun : détection, gestionnaire de paquets, noms des dépendances et conditionnement. Le terminal et GTK devront continuer à réutiliser les mêmes validations. La disponibilité d’un gestionnaire de paquets ne suffit pas à déclarer une distribution compatible.

Une mise en œuvre progressive pourrait suivre ces étapes :

1. Définir les responsabilités des adaptateurs système en conservant le fonctionnement Arch existant.
2. Ajouter une seule nouvelle famille, avec ses noms de paquets et ses commandes de diagnostic et d’installation explicites.
3. Tester les plans, les refus et la gestion des erreurs sur des données fictives, puis valider les interventions dans un environnement jetable autorisé.
4. Valider les parcours réels du terminal, de GTK, des sauvegardes et de l’annulation, ainsi que les paquets installés, avant d’annoncer la prise en charge.

Conserver le parcours aperçu, confirmation, revalidation, sauvegarde, application et vérification. Aucun adaptateur ne doit ajouter d’installation au démarrage ni contourner les confirmations. Les noms de paquets et les commandes des nouvelles familles restent à rechercher et à vérifier lors de leur implémentation.

Cette proposition ne modifie pas les restrictions du code, n’ajoute aucune compatibilité macOS et n’autorise aucune installation sur la machine de développement. Elle est consignée uniquement pour une évolution éventuelle, sans changement applicatif ni test exécuté.

## Suite proposée

- Valider l’intégration Stow et les parcours GTK sur Arch Linux puis sur des distributions dérivées identifiées.
- Tester le clonage réseau et l’installation des dépendances dans une machine virtuelle jetable.
- Valider la construction du paquet Arch et son lanceur de bureau, désormais préparés dans la chaîne GitHub.
- Valider le tableau GTK d’activation : lisibilité des chemins longs, filtres, clavier et volumes importants.
- Ouvrir une configuration dans l’éditeur choisi, après définition du parcours correspondant.
- Préparer les mises à jour Git : vérifier les modifications locales, afficher la révision proposée et expliquer que les liens actifs changent immédiatement ; aucune mise à jour silencieuse.
- Proposer l’installation facultative des applications configurées, à partir d’un catalogue explicite.
- Ajouter ensuite la prise en charge contrôlée des dépôts privés et des règles Stow particulières.

## Références

Le [manuel GNU Stow](https://www.gnu.org/software/stow/manual/stow.html) décrit les liens, les conflits et les règles implicites. Les fiches Arch de [python-gobject](https://archlinux.org/packages/extra/x86_64/python-gobject/) et [GTK4](https://archlinux.org/packages/extra/x86_64/gtk4/) servent de références pour les composants graphiques.
