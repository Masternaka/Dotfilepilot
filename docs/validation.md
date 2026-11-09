# Validation et reprise

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

Utiliser d’abord une machine de test et un dépôt fictif ; ne pas commencer avec les configurations personnelles.

1. Installer le projet et ses composants par les mécanismes habituels de la machine de test.
2. Lancer `DOTFILEPILOT_TEST_STOW=1 make test` et `make check`.
3. Ouvrir GTK ; vérifier navigation, clavier, sélection, erreurs et confirmation.
4. Cloner un dépôt HTTPS public fictif dans une destination absente ; vérifier qu’aucun script n’a été lancé.
5. Activer un paquet contenant `.config/exemple/settings` vers un dossier cible jetable.
6. Refaire avec un fichier préexistant ; confirmer sa sauvegarde, puis annuler et comparer son contenu et ses permissions.
7. Remplacer un lien déployé par un autre fichier ; vérifier que l’annulation refuse de l’écraser.
8. Modifier la source ou la destination après l’aperçu ; vérifier que l’activation refuse un aperçu obsolète.
9. Dans une machine virtuelle jetable, tester `dependances --appliquer`, le refus de confirmation, les erreurs sudo et pacman, puis le diagnostic après installation.

Les actions réelles de cette recette restent à effectuer. Aucun résultat natif Arch, GTK, Stow ou réseau n’est revendiqué.

## Reprendre le travail

La prochaine étape est de publier la correction après autorisation, puis de vérifier une nouvelle exécution GitHub construite depuis cette révision. Relancer uniquement l’ancienne exécution ne lui ajouterait pas le correctif. La recette et le lanceur Arch sont préparés ; la construction et l’installation du paquet restent à valider, suivies de la recette sur Omarchy. Les mises à jour Git restent à développer. Aucun commit, push, paquet publié ni installation sur la machine actuelle n’a été effectué par l’assistant pour cette correction.
