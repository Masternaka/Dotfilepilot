"""Préparation des données d’aperçu, sans GTK ni accès aux fichiers."""

from pathlib import Path

from .system import PilotError
from .monitoring import STATES


STATUSES = {"nouveau": "Créer le lien", "actif": "Déjà actif",
            "sauvegarder": "Sauvegarder puis créer le lien"}


def activation_view(plan, status=None):
    """Group links by their source package; counts always cover the entire plan."""
    if status is not None and status not in STATUSES:
        raise PilotError("Filtre d’aperçu inconnu.")
    repository = Path(plan["repository"])
    groups = {name: [] for name in plan["packages"]}
    counts = dict.fromkeys(STATUSES, 0)
    for entry in plan["entries"]:
        try:
            package = Path(entry["source"]).relative_to(repository).parts[0]
        except (ValueError, IndexError) as error:
            raise PilotError("Source hors du dépôt dans l’aperçu.") from error
        if package not in groups or entry["status"] not in STATUSES:
            raise PilotError("Configuration ou état inconnu dans l’aperçu.")
        counts[entry["status"]] += 1
        if status is None or entry["status"] == status:
            groups[package].append({"source": entry["source"], "target": entry["target"],
                                    "status": entry["status"], "action": STATUSES[entry["status"]]})
    return {"counts": counts, "total": sum(counts.values()),
            "visible": sum(len(rows) for rows in groups.values()),
            "groups": [{"package": name, "entries": sorted(rows, key=lambda row: row["target"])}
                       for name, rows in sorted(groups.items()) if rows]}


def activation_table(plan, status=None):
    """Prepare plain row data off the UI thread, without creating GTK objects."""
    view = activation_view(plan, status)
    view["rows"] = [(group["package"], entry)
                    for group in view["groups"] for entry in group["entries"]]
    return view


def current_state_text(report):
    lines = ["Observation : " + report["observed_at"],
             "Lecture seule — observations par déploiement, sans réparation automatique.",
             "Seuls les liens connus des journaux non annulés sont examinés. "
             "Un même chemin peut apparaître dans plusieurs déploiements.", "",
             " ; ".join(f"{title} : {report['counts'][status]}" for status, title in STATES.items()),
             f"Déploiements annulés non examinés : {report['cancelled']}."]
    if not report["deployments"]:
        lines.append("\nAucun déploiement non annulé à examiner.")
    states = {"preparation": "Préparation", "application": "Application en cours",
              "actif": "Actif", "interrompu": "Interrompu"}
    for deployment in report["deployments"]:
        lines.append("\nDéploiement : " + deployment["identifier"])
        if deployment["error"]:
            lines.append("Observation impossible : " + deployment["error"])
            continue
        lines.extend(["État enregistré : " + states[deployment["state"]],
                      "Dépôt : " + deployment["repository"], "Cible : " + deployment["target"]])
        if not deployment["entries"]:
            lines.append("Aucun lien restant à examiner dans ce journal.")
        for entry in deployment["entries"]:
            origin = ("Déjà actif avant ce déploiement" if entry["origin"] == "preexistant"
                      else "Intervention journalisée ; création effective non garantie en cas d’interruption")
            lines.extend(["\n" + STATES[entry["status"]] + " — " + origin,
                          "Destination : " + entry["target"], "Source attendue : " + entry["source"]])
            if entry["link"] is not None:
                lines.append("Lien observé : " + entry["link"])
            if entry["source_error"]:
                lines.append("Source indisponible : " + entry["source_error"])
            if entry["error"]:
                lines.append("Observation impossible : " + entry["error"])
    return "\n".join(lines)


def repository_status_text(report):
    import json

    def path(value):
        return json.dumps(value, ensure_ascii=False)

    lines = ["Observation : " + report["observed_at"], "Dépôt : " + report["repository"],
             "Branche : " + ("Révision détachée" if report["detached"] else report["branch"]),
             "Révision : " + (report["revision"] or "Aucun commit"),
             "Lecture locale uniquement, sans mise à jour ni vérification du serveur distant.",
             "Si des liens sont actifs, déplacer ou supprimer ce dépôt peut les casser ; "
             "modifier ses fichiers modifie aussi les configurations liées."]
    if report["external_filters_disabled"]:
        lines.append("Les filtres externes ont été neutralisés : les différences peuvent varier "
                     "par rapport à Git utilisé avec ces filtres.")
    labels = {".": "Inchangé", "M": "Modifié", "A": "Ajouté", "D": "Supprimé",
              "R": "Renommé", "C": "Copié", "T": "Type modifié", "U": "Conflit", "?": "Non suivi"}
    if report["clean"]:
        lines.append("\nAucun changement local détecté (sous-modules et fichiers ignorés exclus).")
    else:
        lines.append(f"\n{len(report['files'])} fichier(s) avec changements :")
        for entry in report["files"]:
            lines.append("\n" + path(entry["path"]))
            if entry["conflict"]:
                lines.append("Conflit à résoudre")
            lines.append("Index : " + labels.get(entry["index"], entry["index"])
                         + " ; dossier de travail : " + labels.get(entry["worktree"], entry["worktree"]))
            if entry["original_path"] is not None:
                lines.append("Ancien chemin : " + path(entry["original_path"]))
    return "\n".join(lines)
