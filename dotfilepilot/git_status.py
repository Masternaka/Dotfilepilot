"""État Git local à la demande, sans actualisation, filtre externe ou verrou d’index."""

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess

from .system import PilotError


def git_read(repository, arguments, overrides=(), allow_missing=False):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
               GIT_OPTIONAL_LOCKS="0", GIT_ALLOW_PROTOCOL="", GIT_NO_LAZY_FETCH="1",
               GIT_NO_REPLACE_OBJECTS="1")
    command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c",
               "core.hooksPath=" + os.devnull, "-c", "gc.auto=0", "-c", "maintenance.auto=false"]
    for key, value in overrides:
        command.extend(["-c", key + "=" + value])
    try:
        result = subprocess.run(command + list(arguments), cwd=repository, env=env,
                                shell=False, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PilotError("Lecture Git impossible : " + str(error)) from error
    if result.returncode != 0 and not (allow_missing and result.returncode == 1):
        raise PilotError("Lecture Git impossible : " + result.stderr.decode("utf-8", errors="replace")[-4000:])
    return result.stdout


def parse_status(output):
    """Porcelain v2 -z keeps spaces, tabs and newlines inside filenames intact."""
    report = {"branch": None, "revision": None, "detached": False, "files": []}
    has_revision = False
    records = iter(output.split(b"\x00"))
    for record in records:
        if not record:
            continue
        if record.startswith(b"# branch.oid "):
            has_revision = True
            value = record[len(b"# branch.oid "):].decode("ascii")
            report["revision"] = None if value == "(initial)" else value
        elif record.startswith(b"# branch.head "):
            value = record[len(b"# branch.head "):].decode("utf-8", errors="backslashreplace")
            report["detached"] = value == "(detached)"
            report["branch"] = None if report["detached"] else value
        elif record.startswith((b"1 ", b"2 ", b"u ", b"? ")):
            tag = record[:1]
            if tag == b"?":
                xy, path = "??", record[2:]
            else:
                fields = record.split(b" ", {b"1": 8, b"2": 9, b"u": 10}[tag])
                if len(fields) != {b"1": 9, b"2": 10, b"u": 11}[tag]:
                    raise PilotError("Réponse Git incomplète.")
                xy, path = fields[1].decode("ascii"), fields[-1]
            entry = {"path": path.decode("utf-8", errors="backslashreplace"),
                     "index": xy[0], "worktree": xy[1], "conflict": tag == b"u",
                     "original_path": None}
            if tag == b"2":
                original = next(records, None)
                if original is None:
                    raise PilotError("Renommage Git incomplet.")
                entry["original_path"] = original.decode("utf-8", errors="backslashreplace")
            report["files"].append(entry)
        elif not record.startswith(b"# "):
            raise PilotError("Réponse Git non reconnue.")
    if not has_revision or (report["branch"] is None and not report["detached"]):
        raise PilotError("Branche ou révision Git introuvable dans la réponse.")
    return report


def repository_status(repository):
    try:
        repository = Path(repository).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise PilotError("Dossier du dépôt indisponible : " + str(error)) from error
    if not repository.is_dir():
        raise PilotError("Le dépôt doit être un dossier existant.")
    location = git_read(repository, ["rev-parse", "--is-inside-work-tree", "--show-prefix"])
    if location != b"true\n\n":
        raise PilotError("Choisir la racine du dépôt Git, pas un sous-dossier.")
    # A clean/process filter can otherwise execute while Git compares tracked files.
    keys = git_read(repository, ["config", "--includes", "--null", "--name-only", "--get-regexp",
                                 r"^filter\..*\.(clean|process|required)$"], allow_missing=True)
    drivers = set()
    for key in keys.split(b"\x00"):
        if key:
            match = re.fullmatch(r"filter\.(.*)\.(?:clean|process|required)", os.fsdecode(key), re.DOTALL)
            if not match:
                raise PilotError("Configuration de filtre Git non reconnue.")
            drivers.add(match.group(1))
    overrides = [("filter." + name + "." + option, value) for name in sorted(drivers)
                 for option, value in (("clean", ""), ("process", ""), ("required", "false"))]
    output = git_read(repository, ["status", "--porcelain=v2", "--branch", "-z",
                                    "--untracked-files=all", "--ignore-submodules=all", "--no-renames"], overrides)
    report = parse_status(output)
    report.update(repository=str(repository), observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  clean=not report["files"], external_filters_disabled=bool(drivers))
    return report
