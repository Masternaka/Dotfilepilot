"""Préparer les fichiers makepkg, sans construire ni installer de paquet."""

import argparse
import ast
import hashlib
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def project_version():
    tree = ast.parse((ROOT / 'dotfilepilot/__init__.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == '__version__'
                                               for target in node.targets):
            version = ast.literal_eval(node.value)
            if isinstance(version, str) and re.fullmatch(r'[0-9][A-Za-z0-9.+]*', version):
                return version
    raise ValueError('Version du projet absente ou incompatible avec le format Arch.')


def prepare(source, destination, release):
    if not re.fullmatch(r'[1-9][0-9]*', release):
        raise ValueError('La révision Arch doit être un entier strictement positif.')
    version = project_version()
    if source.name != 'dotfilepilot-' + version + '.tar.gz' or not source.is_file():
        raise ValueError('Choisir l’archive source construite pour Dotfilepilot ' + version + '.')
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    template = (ROOT / 'packaging/arch/PKGBUILD.in').read_text(encoding='utf-8')
    for key, value in (('@VERSION@', version), ('@PKGREL@', release), ('@SOURCE_SHA256@', checksum)):
        if key not in template:
            raise ValueError('Modèle de recette incomplet : ' + key)
        template = template.replace(key, value)
    if re.search(r'@[A-Z_]+@', template):
        raise ValueError('Le modèle contient des paramètres non remplacés.')
    # Refuser les sorties existantes pour préserver fichiers personnels et anciennes constructions.
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, destination / source.name)
    (destination / 'PKGBUILD').write_text(template, encoding='utf-8')
    print('Recette et archive préparées dans ' + str(destination) + ' ; aucune construction ni installation.')
    return destination / 'PKGBUILD'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Archive tar.gz déjà construite et vérifiée.')
    parser.add_argument('--output', type=Path, required=True, help='Nouveau dossier de préparation.')
    parser.add_argument('--pkgrel', default='1', help='Révision Arch positive (numéro de run en CI).')
    args = parser.parse_args()
    try:
        prepare(args.source, args.output, args.pkgrel)
    except (OSError, ValueError, SyntaxError) as error:
        print('Préparation impossible : ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
