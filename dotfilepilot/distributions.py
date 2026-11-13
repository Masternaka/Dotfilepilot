"""Adaptateurs des paquets système ; aucune commande exécutée dans ce module."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PackageAdapter:
    manager: str
    packages: tuple
    query: tuple
    install: tuple

    def installed(self, output):
        if self.manager != "apt-get":
            return set(output.splitlines())
        installed = set()
        for line in output.splitlines():
            fields = line.split("\t")
            if len(fields) != 2 or not fields[0] or len(fields[1]) != 3:
                raise ValueError("Réponse dpkg-query invalide ; état des paquets inconnu.")
            # Le souhait (installation/conservation) n'est pas l'état réel.
            # Refuser aussi les paquets marqués comme nécessitant une réparation.
            if fields[1][1:] == "i ":
                installed.add(fields[0])
        return installed


ADAPTERS = {
    "arch": PackageAdapter("pacman", ("git", "stow", "python", "python-gobject", "gtk4"),
                           ("pacman", "-Qq"), ("pacman", "-S", "--needed")),
    "debian": PackageAdapter("apt-get", ("git", "stow", "python3", "python3-gi", "gir1.2-gtk-4.0"),
                             ("dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\n"),
                             ("apt-get", "install")),
    "fedora": PackageAdapter("dnf", ("git", "stow", "python3", "python3-gobject", "gtk4"),
                             ("rpm", "-qa", "--queryformat", "%{NAME}\n"), ("dnf", "install")),
}
