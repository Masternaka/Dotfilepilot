# Conception de Dotfilepilot

## Objectif retenu

Créer un gestionnaire de dotfiles pour Omarchy / Arch Linux, sur le modèle de Sambapilot : moteur Python commun, terminal autonome et interface GTK4. Le choix Arch a été confirmé le 9 novembre 2026.

L’utilisateur doit pouvoir préparer sa machine, cloner son dépôt, choisir ses configurations, consulter les conflits, activer les liens et revenir à son état précédent pour les fichiers concernés.

## Architecture présente

- `system.py` : diagnostic, identification Arch, plan de dépendances, installation terminal et clonage HTTPS.
- `deployments.py` : inventaire, analyse Stow isolée, empreintes des sources et destinations, sauvegardes, journal et annulation.
- `cli.py` : commandes et confirmation explicite.
- `gui.py` / `gtk_app.py` : chargement GTK facultatif, navigation et opérations en arrière-plan.
- `tests/` : scénarios isolés avec fichiers temporaires, commandes simulées et intégration Stow facultative.
- `.github/workflows/ci.yml` et `packaging/arch/` : chaîne de tests, archives Python et paquet Arch, configurée mais encore à valider sur GitHub.

Le moteur n’exécute pas de shell. Le clonage désactive les hooks, les modèles Git, les configurations Git globales et les sous-modules. Cette première version ne gère ni authentification privée, ni secrets enregistrés, ni exécution des programmes du dépôt.

Stow est invoqué avec un dépôt et une cible explicites ainsi que `--no-folding`. Le premier calcul se fait dans un dossier temporaire vide ; les liens obtenus servent à l’aperçu réel. Les conflits sont sauvegardés avant l’application, sans utilisation de `--adopt`. Une annulation retire seulement les liens créés par le déploiement concerné et restaure ses sauvegardes. Les liens corrects qui existaient déjà ne lui appartiennent pas.

## Parcours graphique

1. **Accueil et dépendances** : consulter le diagnostic et la commande d’installation dans un terminal.
2. **Dépôt** : préparer un clonage ou analyser un dossier existant.
3. **Configurations** : cocher les paquets et choisir la cible.
4. **Aperçu** : examiner le résultat, cocher l’autorisation et appliquer.
5. **Sauvegardes et annulation** : consulter les identifiants et préparer une restauration.

Une modification des champs ou de la sélection invalide l’autorisation. Le moteur recalcule l’aperçu avant l’activation. Pendant une opération en cours, la fermeture de la fenêtre est bloquée pour ne pas interrompre volontairement une écriture.

## Limites de la première version

Le code constitue une version de développement, pas une version prête pour les configurations personnelles. La validation native Stow, GTK, pacman, sudo et Git réseau reste à réaliser. Les protections visent les erreurs courantes et les changements entre aperçu et application ; elles ne garantissent pas une transaction atomique face à un autre programme qui modifie simultanément les mêmes chemins.

Le mode utilisateur vise le dossier personnel. Les modèles destinés à `/etc`, comme Samba et pacman, exigent un futur parcours séparé. Aucun privilège administrateur n’est utilisé pour Stow. Les répertoires vides créés par Stow ne sont pas supprimés lors de l’annulation.

## Suite proposée

- Valider l’intégration Stow et les parcours GTK sur une machine Arch de test, puis Omarchy.
- Tester le clonage réseau et l’installation des dépendances dans une machine virtuelle jetable.
- Valider la construction du paquet Arch et son lanceur de bureau, désormais préparés dans la chaîne GitHub.
- Améliorer l’aperçu GTK : tableau par application, filtres, conflits et sauvegardes lisibles.
- Afficher l’état Git du dépôt et ouvrir une configuration dans l’éditeur choisi.
- Préparer les mises à jour Git : vérifier les modifications locales, afficher la révision proposée et expliquer que les liens actifs changent immédiatement ; aucune mise à jour silencieuse.
- Proposer l’installation facultative des applications configurées, à partir d’un catalogue explicite.
- Ajouter ensuite la prise en charge contrôlée des dépôts privés et des règles Stow particulières.

## Références

Le [manuel GNU Stow](https://www.gnu.org/software/stow/manual/stow.html) décrit les liens, les conflits et les règles implicites. Les fiches Arch de [python-gobject](https://archlinux.org/packages/extra/x86_64/python-gobject/) et [GTK4](https://archlinux.org/packages/extra/x86_64/gtk4/) servent de références pour les composants graphiques.
