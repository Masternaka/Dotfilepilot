"""Observation à la demande des liens journalisés, sans écriture ni programme externe."""

from datetime import datetime, timezone
import os
from pathlib import Path
import stat

from . import deployments as deploy
from .system import PilotError


STATES = {"correct": "Lien correct", "casse": "Lien cassé", "autre_lien": "Lien remplacé",
          "remplace": "Remplacé par un fichier ou dossier", "absent": "Lien absent",
          "indisponible": "Chemin indisponible"}


def kind(path):
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return "absent"
    if stat.S_ISLNK(mode):
        return "lien"
    if stat.S_ISDIR(mode):
        return "dossier"
    return "fichier" if stat.S_ISREG(mode) else "special"


def absolute_path(value):
    if (not isinstance(value, str) or "\x00" in value or not Path(value).is_absolute()
            or ".." in Path(value).parts):
        raise PilotError("Chemin invalide dans le journal.")
    return Path(value)


def check_root(path):
    # Do not traverse a root redirected since deployment, including its ancestors.
    for parent in reversed((path,) + tuple(path.parents)):
        if kind(parent) != "dossier":
            raise PilotError("Dossier absent, redirigé ou non répertoire : " + str(parent))


def observe(entry, root, repository):
    result = {"target": entry["target"], "source": entry["source"],
              "origin": "preexistant" if entry["status"] == "actif" else "journalise",
              "source_state": "disponible", "source_error": None, "error": None,
              "link": None}
    target, source = Path(entry["target"]), Path(entry["source"])
    try:
        check_root(repository)
        deploy.safe_parents(source, repository)
        if kind(source) != "fichier":
            raise PilotError("Source absente, symbolique ou non régulière : " + str(source))
    except (PilotError, OSError, RuntimeError) as error:
        result.update(source_state="indisponible", source_error=str(error))
    try:
        check_root(root)
        deploy.safe_parents(target, root)
        current = kind(target)
        if current == "lien":
            result["link"] = os.readlink(target)
            try:
                resolved = target.resolve(strict=True)
            except FileNotFoundError:
                result["status"] = "casse"
            else:
                expected_link = Path(os.path.normpath(os.path.join(str(target.parent), result["link"]))) == source
                if result["source_state"] != "disponible" and (expected_link or resolved == source):
                    result["status"] = "indisponible"
                else:
                    result["status"] = "correct" if resolved == source else "autre_lien"
        else:
            result["status"] = "absent" if current == "absent" else "remplace"
    except (PilotError, OSError, RuntimeError) as error:
        result.update(status="indisponible", error=str(error))
    return result


def current_state(store=None):
    """Observe each unfinished journal separately; no ownership is inferred from links."""
    report = {"observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "deployments": [], "counts": dict.fromkeys(STATES, 0), "cancelled": 0}
    for identifier in reversed(deploy.history(store)):
        item = {"identifier": identifier, "entries": [], "error": None}
        try:
            data = deploy.read_journal(identifier, store)
            if data["state"] == "annule":
                report["cancelled"] += 1
                continue
            plan = data["plan"]
            root, repository = absolute_path(plan["target"]), absolute_path(plan.get("repository"))
            entries = plan.get("entries")
            if not isinstance(entries, list):
                raise PilotError("Liste des liens absente du journal.")
            # Validate all entries before inspecting any of their paths.
            seen = set()
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("status") not in ("actif", "nouveau", "sauvegarder"):
                    raise PilotError("Lien invalide dans le journal.")
                target, source = absolute_path(entry.get("target")), absolute_path(entry.get("source"))
                if root not in target.parents or repository not in source.parents or target in seen:
                    raise PilotError("Lien hors périmètre ou répété dans le journal.")
                seen.add(target)
            pending = {(record["target"], record["source"]) for record in data["records"]}
            item.update(state=data["state"], repository=str(repository), target=str(root))
            for entry in entries:
                if entry["status"] == "actif" or (entry["target"], entry["source"]) in pending:
                    observation = observe(entry, root, repository)
                    item["entries"].append(observation)
                    report["counts"][observation["status"]] += 1
        except (PilotError, OSError, ValueError, RuntimeError) as error:
            item["error"] = str(error)
        report["deployments"].append(item)
    return report
