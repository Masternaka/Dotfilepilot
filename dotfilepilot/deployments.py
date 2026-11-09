"""Aperçus Stow, sauvegardes et annulation des seuls liens journalisés."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid

from .system import PilotError, run


def present(path):
    return path.exists() or path.is_symlink()


def fingerprint(path):
    if path.is_symlink():
        return ["lien", os.readlink(path)]
    if not path.exists():
        return ["absent"]
    if path.is_file():
        info = path.stat()
        if info.st_size > 20 * 1024 * 1024:
            raise PilotError("Fichier supérieur à 20 Mio : " + str(path))
        return ["fichier", hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(info.st_mode)]
    raise PilotError("Fichier spécial ou dossier en conflit : " + str(path))


def safe_parents(path, root):
    parent = path.parent
    while parent != root:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise PilotError("Parent redirigé ou non répertoire : " + str(parent))
        if parent == parent.parent:
            raise PilotError("Chemin hors de la cible.")
        parent = parent.parent


def roots(repository, target):
    repository = Path(repository).expanduser().resolve(strict=True)
    raw_target = Path(target).expanduser().absolute()
    if raw_target.is_symlink():
        raise PilotError("La cible ne peut pas être un lien symbolique.")
    target = raw_target.resolve(strict=True)
    if not repository.is_dir() or not target.is_dir():
        raise PilotError("Le dépôt et la cible doivent être des dossiers existants.")
    if repository == target or repository in target.parents or target == Path("/"):
        raise PilotError("Cible invalide ou située dans le dépôt.")
    for system_root in ("/etc", "/usr", "/bin", "/sbin", "/boot", "/root", "/opt"):
        boundary = Path(system_root).resolve()
        if target == boundary or boundary in target.parents:
            raise PilotError("Les configurations système ne sont pas prises en charge.")
    return repository, target


def packages(repository):
    repository = Path(repository).expanduser().resolve(strict=True)
    return sorted(p.name for p in repository.iterdir()
                  if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")
                  and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", p.name)
                  and any(c.name.startswith(".") for c in p.iterdir()))


def check_source(repository, selected):
    # Stow's implicit configuration must never extend the reviewed scope.
    for path in (repository / ".stowrc", Path.home() / ".stowrc",
                 Path.home() / ".stow-global-ignore"):
        if present(path):
            raise PilotError("Règle Stow implicite à examiner manuellement : " + str(path))
    snapshots = {}
    for name in selected:
        if name not in packages(repository):
            raise PilotError("Paquet inconnu ou sans arborescence de dotfiles : " + name)
        source = repository / name
        for path in [source] + sorted(source.rglob("*")):
            if path.name in (".stow-local-ignore", ".stowrc", ".git"):
                raise PilotError("Règle ou dépôt imbriqué non pris en charge : " + str(path))
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise PilotError("Source symbolique ou spéciale refusée : " + str(path))
            relative = path.relative_to(source)
            if relative.parts and not relative.parts[0].startswith("."):
                # Documentation at the package root is ignored by default in
                # many repos. It must not silently become ~/README or ~/script.
                if path.is_file() and path.parent == source and re.match(r"^(README|LICENSE|COPYING)(\.|$)", path.name, re.I):
                    continue
                raise PilotError("Contenu hors dotfiles à examiner : " + str(path))
            if path.is_file():
                snapshots[str(path)] = fingerprint(path)
            if len(snapshots) > 10000:
                raise PilotError("Trop de fichiers pour cette version (10 000 maximum).")
    return snapshots


def stow_command(repository, target, selected):
    return ["stow", "--dir=" + str(repository), "--target=" + str(target),
            "--no-folding", "--stow", "--"] + list(selected)


def preview(repository, target, selected):
    repository, target = roots(repository, target)
    selected = sorted(set(selected))
    if not selected:
        raise PilotError("Sélectionner au moins une configuration.")
    snapshot = check_source(repository, selected)
    entries = []
    # Stow itself determines ignored files. Its real deployment is isolated in
    # a private empty directory; no user configuration is touched here.
    with tempfile.TemporaryDirectory(prefix="dotfilepilot-preview-") as temp:
        shadow = Path(temp).resolve()
        run(stow_command(repository, shadow, selected), cwd=shadow)
        for path in sorted(shadow.rglob("*")):
            if not path.is_symlink():
                continue
            relative = path.relative_to(shadow)
            source = path.resolve(strict=True)
            if str(source) not in snapshot:
                raise PilotError("Lien Stow inattendu : " + str(path))
            destination = target / relative
            if destination == repository or repository in destination.parents or destination in repository.parents:
                raise PilotError("Déploiement vers le dépôt refusé.")
            safe_parents(destination, target)
            current = fingerprint(destination)
            status = "actif" if destination.is_symlink() and destination.resolve() == source else (
                "nouveau" if current == ["absent"] else "sauvegarder")
            entries.append({"target": str(destination), "source": str(source),
                            "before": current, "status": status})
    if not entries:
        raise PilotError("Stow n’a prévu aucun lien.")
    return {"repository": str(repository), "target": str(target), "packages": selected,
            "snapshot": snapshot, "entries": entries}


def state_root():
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "dotfilepilot"


@contextmanager
def locked(store):
    store = Path(store).absolute()
    if store.is_symlink():
        raise PilotError("Dossier de sauvegarde symbolique refusé.")
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    if store.stat().st_uid != os.getuid() or stat.S_IMODE(store.stat().st_mode) & 0o077:
        raise PilotError("Le dossier de sauvegarde doit être privé (0700) et vous appartenir.")
    fd = os.open(store / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise PilotError("Une opération Dotfilepilot est déjà en cours.") from error
        yield store
    finally:
        os.close(fd)


def save(journal, data):
    path = journal / "journal.json"
    temporary = journal / "journal.tmp"
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def apply(plan, store=None):
    with locked(store or state_root()) as store:
        for item in plan["entries"]:
            destination = Path(item["target"])
            if destination == store or store in destination.parents or destination in store.parents:
                raise PilotError("Les sauvegardes de Dotfilepilot ne peuvent pas être déployées.")
        if preview(plan["repository"], plan["target"], plan["packages"]) != plan:
            raise PilotError("L’état a changé depuis l’aperçu. Recommencer l’analyse.")
        if all(item["status"] == "actif" for item in plan["entries"]):
            return "Configurations déjà actives ; aucune modification."
        journal = store / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
        journal.mkdir(mode=0o700)
        data = {"plan": plan, "state": "preparation", "records": [], "restored": []}
        save(journal, data)
        try:
            for item in plan["entries"]:
                if item["status"] == "actif":
                    continue
                record = dict(item, backup=None)
                if item["status"] == "sauvegarder":
                    record["backup"] = str(len(data["records"])) + ".backup"
                data["records"].append(record)
                save(journal, data)
                if record["backup"]:
                    os.replace(item["target"], journal / record["backup"])
            data["state"] = "application"
            save(journal, data)
            with tempfile.TemporaryDirectory(prefix="dotfilepilot-run-") as temp:
                run(stow_command(plan["repository"], plan["target"], plan["packages"]), cwd=temp)
            for item in plan["entries"]:
                target = Path(item["target"])
                if not target.is_symlink() or target.resolve() != Path(item["source"]):
                    raise PilotError("Lien attendu absent : " + str(target))
            data["state"] = "actif"
            save(journal, data)
        except (PilotError, OSError) as error:
            data["state"] = "interrompu"
            save(journal, data)
            raise PilotError("Déploiement interrompu. Sauvegardes et reprise : " + str(journal)
                             + "\n" + str(error)) from error
        return journal.name


def history(store=None):
    store = Path(store or state_root())
    if not store.exists():
        return []
    return sorted(p.name for p in store.iterdir()
                  if not p.is_symlink() and p.is_dir() and (p / "journal.json").is_file())


def preview_undo(identifier, store=None):
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", identifier):
        raise PilotError("Identifiant de déploiement invalide.")
    journal = Path(store or state_root()) / identifier
    if journal.is_symlink() or (journal / "journal.json").is_symlink():
        raise PilotError("Journal symbolique refusé.")
    data = json.loads((journal / "journal.json").read_text())
    if data["state"] == "annule":
        raise PilotError("Déploiement déjà annulé.")
    target_root = Path(data["plan"]["target"])
    if target_root.is_symlink() or not target_root.is_dir():
        raise PilotError("Cible du journal indisponible ou redirigée.")
    for record in data["records"]:
        target = Path(record["target"])
        if target_root not in target.parents:
            raise PilotError("Journal hors périmètre.")
        safe_parents(target, target_root)
        if present(target) and not (target.is_symlink() and target.resolve() == Path(record["source"])):
            # Crash before moving a conflict: that original file remains safe.
            if record["backup"] and fingerprint(target) == record["before"]:
                continue
            raise PilotError("Fichier modifié depuis le déploiement, annulation bloquée : " + str(target))
        if record["backup"]:
            backup = journal / record["backup"]
            if backup.parent != journal:
                raise PilotError("Sauvegarde hors journal.")
            if present(backup) and fingerprint(backup) != record["before"]:
                raise PilotError("Sauvegarde modifiée : " + str(backup))
            if not present(backup) and not (present(target) and fingerprint(target) == record["before"]):
                raise PilotError("Sauvegarde manquante : " + str(backup))
    return data


def undo(identifier, reviewed, store=None):
    with locked(store or state_root()) as store:
        data = preview_undo(identifier, store)
        if data != reviewed:
            raise PilotError("Le journal a changé : recalculer l’aperçu.")
        journal = store / identifier
        # Each completed record is saved, so interrupted undo can be resumed.
        while data["records"]:
            record = data["records"][-1]
            target = Path(record["target"])
            if target.is_symlink() and target.resolve() == Path(record["source"]):
                target.unlink()
            if record["backup"] and present(journal / record["backup"]):
                backup = journal / record["backup"]
                if backup.is_symlink():
                    target.symlink_to(os.readlink(backup))
                else:
                    shutil.copy2(backup, target, follow_symlinks=False)
            data["restored"].append(data["records"].pop())
            save(journal, data)
        data["state"] = "annule"
        save(journal, data)
        return "Liens retirés et configurations restaurées. Sauvegardes conservées."
