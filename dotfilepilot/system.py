"""Diagnostic et actions explicites, sans commande shell."""

import os
import platform
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile
from urllib.parse import urlsplit

from .distributions import ADAPTERS


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


def distribution():
    """Lire l'identité déclarative ; un gestionnaire présent ne suffit jamais."""
    unknown = {"id": "", "version": "", "variante": "", "famille": None,
               "interventions": False, "motif": "Identité Linux absente, illisible ou non reconnue."}
    if platform.system() != "Linux":
        return dict(unknown, motif="Les interventions nécessitent Linux.")
    content = None
    for release in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            content = Path(release).read_text(encoding="utf-8")
            break
        except FileNotFoundError:
            continue
        except (OSError, UnicodeError):
            return unknown
    if content is None:
        return unknown
    try:
        values = {}
        for line in content.splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            if key.strip() not in ("ID", "ID_LIKE", "VERSION_ID", "VARIANT_ID"):
                continue
            parsed = shlex.split(value, comments=True)
            if len(parsed) != 1:
                return unknown
            values[key.strip()] = parsed[0]
    except ValueError:
        return unknown
    identity = values.get("ID", "")
    # ID est prioritaire ; ID_LIKE est une liste ordonnée de mots exacts.
    candidates = [identity] + values.get("ID_LIKE", "").split()
    family = next((item for item in candidates if item in ADAPTERS), None)
    variant = values.get("VARIANT_ID", "")
    result = dict(unknown, id=identity, version=values.get("VERSION_ID", ""),
                  variante=variant, famille=family)
    if family:
        result.update(interventions=True, motif="")
    if family == "fedora" and (variant == "atomic" or variant.endswith("-atomic") or variant in (
            "silverblue", "kinoite", "sericea", "onyx", "coreos", "sway-atomic",
            "budgie-atomic", "cosmic-atomic") or Path("/run/ostree-booted").exists()):
        result.update(interventions=False,
                      motif="Les éditions Fedora Atomic / OSTree ne sont pas prises en charge.")
    return result


def is_arch():
    return distribution()["famille"] == "arch"


def require_supported():
    identity = distribution()
    if not identity["interventions"]:
        raise PilotError(identity["motif"] + " Cibles : Arch, Debian et Fedora classique.")
    if os.geteuid() == 0:
        raise PilotError("Lancer Dotfilepilot avec votre compte utilisateur, sans sudo.")
    return identity


def diagnostic():
    identity = distribution()
    adapter = ADAPTERS.get(identity["famille"])
    return {"systeme": platform.system(), "arch": identity["famille"] == "arch",
            "distribution": identity,
            "gestionnaire": adapter.manager if adapter else None,
            "outils": {name: shutil.which(name) for name in
                       ("git", "stow", "pacman", "apt-get", "dpkg-query", "dnf", "rpm", "sudo")},
            "paquets_requis": list(adapter.packages) if adapter else []}


def installation_plan():
    identity = require_supported()
    adapter = ADAPTERS[identity["famille"]]
    for tool in (adapter.manager, adapter.query[0]):
        if not shutil.which(tool):
            raise PilotError(tool + " est introuvable ; état des dépendances inconnu.")
    # A failed query is not sufficient evidence of a missing package.
    try:
        installed = adapter.installed(run(list(adapter.query)))
    except ValueError as error:
        raise PilotError(str(error)) from error
    missing = [name for name in adapter.packages if name not in installed]
    return {"distribution": identity, "gestionnaire": adapter.manager, "manquants": missing,
            "commande": list(adapter.install) + missing if missing else []}


def install(plan, graphical=False):
    require_supported()
    if graphical:
        raise PilotError("L’installation se fait dans le terminal pour examiner la transaction système.")
    if installation_plan() != plan:
        raise PilotError("Les dépendances ou le système ont changé : recalculer l’aperçu.")
    if not plan["commande"]:
        return "Tous les composants sont déjà installés."
    elevation = "sudo"
    if not shutil.which(elevation):
        raise PilotError(elevation + " est introuvable ; utiliser le terminal.")
    # Keep the package manager's own dependency, replacement and transaction confirmation.
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
    require_supported()
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
