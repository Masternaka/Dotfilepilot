"""Interface terminal ; les opérations restent explicites."""

import argparse
import json
from pathlib import Path

from . import __version__, deployments as deploy
from .system import (PilotError, clone, clone_plan, diagnostic, install,
                     installation_plan, require_arch)


def show(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def confirm():
    try:
        return input("Appliquer cet aperçu ? Tapez OUI : ") == "OUI"
    except EOFError:
        return False


def parser():
    root = argparse.ArgumentParser(description="Dotfilepilot — configurations Omarchy / Arch Linux")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("diagnostic", help="Consulter les composants disponibles")
    commands.add_parser("gui", help="Ouvrir l’interface GTK4")
    setup = commands.add_parser("dependances", help="Préparer ou installer les composants")
    setup.add_argument("--appliquer", action="store_true")
    copy = commands.add_parser("cloner", help="Cloner un dépôt HTTPS sans exécuter ses scripts")
    copy.add_argument("url")
    copy.add_argument("destination", type=Path)
    copy.add_argument("--appliquer", action="store_true")
    listing = commands.add_parser("inventaire", help="Lister les dossiers candidats à Stow")
    listing.add_argument("depot", type=Path)
    activation = commands.add_parser("activer", help="Préparer ou déployer les liens avec sauvegarde")
    activation.add_argument("depot", type=Path)
    activation.add_argument("paquets", nargs="+")
    activation.add_argument("--cible", type=Path, default=Path.home())
    activation.add_argument("--appliquer", action="store_true")
    commands.add_parser("historique", help="Lister les déploiements locaux")
    revert = commands.add_parser("annuler", help="Préparer ou annuler un déploiement")
    revert.add_argument("identifiant")
    revert.add_argument("--appliquer", action="store_true")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "gui":
            from .gui import launch
            return launch()
        if args.command == "diagnostic":
            show(diagnostic())
        elif args.command == "inventaire":
            show(deploy.packages(args.depot))
        elif args.command == "historique":
            show(deploy.history())
        else:
            action = None
            if args.command == "dependances":
                plan = installation_plan()
                action = lambda: install(plan)
            elif args.command == "cloner":
                plan = clone_plan(args.url, args.destination)
                action = lambda: clone(plan)
            elif args.command == "activer":
                plan = deploy.preview(args.depot, args.cible, args.paquets)
                action = lambda: deploy.apply(plan)
            elif args.command == "annuler":
                plan = deploy.preview_undo(args.identifiant)
                action = lambda: deploy.undo(args.identifiant, plan)
            show(plan)
            if args.appliquer:
                require_arch()
                if confirm():
                    print(action())
                else:
                    print("Opération annulée.")
        return 0
    except (PilotError, OSError, ValueError) as error:
        print("Erreur : " + str(error))
        return 2
