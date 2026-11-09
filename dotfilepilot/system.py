"""Diagnostic et actions explicites, sans commande shell."""

import os
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit


class PilotError(Exception):
    pass


def run(command, cwd=None, capture=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0")
    try:
        result = subprocess.run(command, cwd=cwd, env=env, shell=False,
                                text=True, capture_output=capture, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PilotError(str(error)) from error
    if result.returncode:
        raise PilotError((result.stderr or "La commande a échoué.")[-4000:])
    return result.stdout or ""


def is_arch():
    if platform.system() != "Linux":
        return False
    try:
        values = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines()
                      if "=" in line)
    except OSError:
        return False
    return values.get("ID", "").strip('"') == "arch"


def require_arch():
    if not is_arch():
        raise PilotError("Les interventions sont réservées à Arch Linux / Omarchy.")
    if os.geteuid() == 0:
        raise PilotError("Lancer Dotfilepilot avec votre compte utilisateur, sans sudo.")


def diagnostic():
    return {"systeme": platform.system(), "arch": is_arch(),
            "outils": {name: shutil.which(name) for name in ("git", "stow", "pacman", "pkexec")},
            "paquets_requis": ["git", "stow", "python", "python-gobject", "gtk4"]}


PACKAGES = ("git", "stow", "python", "python-gobject", "gtk4")


def installation_plan():
    require_arch()
    if not shutil.which("pacman"):
        raise PilotError("pacman est introuvable.")
    # A failed query is not sufficient evidence of a missing package.
    installed = set(run(["pacman", "-Qq"]).splitlines())
    missing = [name for name in PACKAGES if name not in installed]
    return {"manquants": missing,
            "commande": ["pacman", "-S", "--needed"] + missing if missing else []}


def install(plan, graphical=False):
    require_arch()
    if graphical:
        raise PilotError("L’installation se fait dans le terminal pour examiner la transaction pacman.")
    if installation_plan() != plan:
        raise PilotError("Les dépendances ont changé : recalculer l’aperçu.")
    if not plan["commande"]:
        return "Tous les composants sont déjà installés."
    elevation = "sudo"
    if not shutil.which(elevation):
        raise PilotError(elevation + " est introuvable ; utiliser le terminal.")
    # Keep pacman's own dependency, replacement and transaction confirmation.
    command = [elevation] + plan["commande"]
    run(command, capture=False)
    if installation_plan()["manquants"]:
        raise PilotError("Installation incomplète ; relancer le diagnostic.")
    return "Dépendances vérifiées après installation."


def clone_plan(url, destination):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not parsed.path.strip("/")
            or any(c.isspace() for c in url)):
        raise PilotError("Utiliser une URL Git HTTPS sans identifiants intégrés.")
    path = Path(destination).expanduser().absolute()
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise PilotError("La destination doit être absente, dans un dossier existant.")
    return {"url": url, "destination": str(path)}


def clone(plan):
    require_arch()
    if clone_plan(plan["url"], plan["destination"]) != plan:
        raise PilotError("Destination modifiée.")
    destination = Path(plan["destination"])
    with tempfile.TemporaryDirectory(prefix=".dotfilepilot-clone-", dir=destination.parent) as temp:
        candidate = Path(temp) / "repository"
        run(["git", "-c", "core.hooksPath=" + os.devnull,
             "-c", "protocol.file.allow=never", "clone", "--template=",
             "--no-recurse-submodules", "--", plan["url"], str(candidate)])
        # Reserve destination without replacing an existing file or directory.
        destination.mkdir(mode=0o700)
        try:
            for child in candidate.iterdir():
                child.rename(destination / child.name)
        except OSError as error:
            raise PilotError("Clonage partiel conservé dans " + str(destination)) from error
    return "Dépôt cloné. Aucun script du dépôt n’a été lancé."
