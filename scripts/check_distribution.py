"""Contrôler les archives construites, sans extraction ni installation."""

import argparse
import configparser
from email.parser import BytesParser
from pathlib import Path
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def check(directory):
    wheels = list(directory.glob('*.whl'))
    sources = list(directory.glob('*.tar.gz'))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError('Un wheel et une archive source uniques sont requis dans le dossier choisi.')
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        metadata_files = [name for name in names if name.endswith('.dist-info/METADATA')]
        if len(metadata_files) != 1:
            raise ValueError('Métadonnées du wheel absentes ou ambiguës.')
        metadata = BytesParser().parsebytes(wheel.read(metadata_files[0]))
        if metadata['Name'] != 'dotfilepilot' or metadata['Requires-Python'] != '>=3.9':
            raise ValueError('Nom ou version Python minimale incorrects.')
        if metadata.get_all('Requires-Dist'):
            raise ValueError('Le moteur et le terminal doivent rester sans dépendance externe.')
        entrypoints = configparser.ConfigParser()
        entrypoints.read_string(wheel.read(metadata_files[0].replace('METADATA', 'entry_points.txt')).decode())
        if entrypoints.get('console_scripts', 'dotfilepilot') != 'dotfilepilot.cli:main':
            raise ValueError('Point d’entrée terminal incorrect.')
        for path in (ROOT / 'dotfilepilot').rglob('*.py'):
            if wheel.read(path.relative_to(ROOT).as_posix()) != path.read_bytes():
                raise ValueError('Source différente dans le wheel : ' + str(path))
        if any(name.startswith(('tests/', 'scripts/', 'docs/')) for name in names):
            raise ValueError('Le wheel contient des fichiers réservés au développement.')
    required = [ROOT / name for name in ('README.md', 'AGENTS.md', 'Makefile', 'pyproject.toml', 'MANIFEST.in', '.gitignore')]
    required += [path for folder, pattern in (('dotfilepilot', '*.py'), ('tests', '*.py'),
                                             ('scripts', '*.py'), ('docs', '*.md'))
                 for path in (ROOT / folder).rglob(pattern)]
    required += [path for folder in ('.github', 'packaging')
                 for path in (ROOT / folder).rglob('*') if path.is_file()]
    with tarfile.open(sources[0], 'r:gz') as archive:
        roots = {name.split('/')[0] for name in archive.getnames()}
        if len(roots) != 1:
            raise ValueError('La distribution source doit avoir un seul dossier racine.')
        prefix = roots.pop() + '/'
        for path in required:
            stream = archive.extractfile(prefix + path.relative_to(ROOT).as_posix())
            if stream is None or stream.read() != path.read_bytes():
                raise ValueError('Fichier absent ou différent dans les sources : ' + str(path))
    print('Wheel et sources complets ; point d’entrée et dépendances vérifiés.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Dossier contenant le wheel et le tar.gz déjà construits.')
    args = parser.parse_args()
    try:
        check(args.directory)
    except (OSError, ValueError, KeyError, configparser.Error, tarfile.TarError, zipfile.BadZipFile) as error:
        print('Conditionnement invalide : ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
