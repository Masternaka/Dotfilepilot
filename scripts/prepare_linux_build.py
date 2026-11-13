"""Préparer les recettes Debian ou Fedora, sans extraction, construction ni installation."""

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_arch_build import project_version


def prepare(source, destination, family, release):
    if family not in ('debian', 'fedora') or not re.fullmatch(r'[1-9][0-9]*', release):
        raise ValueError('Choisir Debian ou Fedora et une révision entière strictement positive.')
    version = project_version()
    if source.name != 'dotfilepilot-' + version + '.tar.gz' or not source.is_file():
        raise ValueError('Choisir l’archive source vérifiée de Dotfilepilot ' + version + '.')
    # Une version de développement doit précéder la version finale dans dpkg et RPM.
    native_version = re.sub(r'\.(dev|a|b|rc)(?=[0-9])', r'~\1', version)
    templates = {}
    for path in (ROOT / 'packaging' / family).glob('*.in'):
        text = path.read_text(encoding='utf-8')
        for key, value in (('@VERSION@', version), ('@NATIVE_VERSION@', native_version), ('@RELEASE@', release)):
            text = text.replace(key, value)
        if re.search(r'@[A-Z_]+@', text):
            raise ValueError('Paramètre de recette non remplacé : ' + str(path))
        templates[path.name[:-3]] = text
    if not templates:
        raise ValueError('Recettes de conditionnement absentes.')
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, destination / source.name)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (destination / 'SHA256SUMS').write_text(digest + '  ' + source.name + '\n', encoding='utf-8')
    recipes = destination / ('debian' if family == 'debian' else 'SPECS')
    recipes.mkdir()
    for name, text in templates.items():
        target = recipes / name
        target.write_text(text, encoding='utf-8')
        if name == 'rules':
            target.chmod(0o755)
    return recipes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--family', choices=('debian', 'fedora'), required=True)
    parser.add_argument('--release', default='1')
    args = parser.parse_args()
    try:
        print('Recettes préparées : ' + str(prepare(args.source, args.output, args.family, args.release)))
    except (OSError, ValueError) as error:
        print('Préparation impossible : ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
