"""Contrôler le paquet installé hors du dépôt, sans intervention système."""

from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    import dotfilepilot
    if ROOT in Path(dotfilepilot.__file__).resolve().parents:
        raise RuntimeError('Le test doit charger le paquet installé, pas les sources.')
    if metadata.version('dotfilepilot') != dotfilepilot.__version__:
        raise RuntimeError('Versions du module et du paquet incohérentes.')
    icons = Path(dotfilepilot.__file__).parent / 'assets/icons'
    for name in ('io.github.dotfilepilot.App.svg', 'io.github.dotfilepilot.App-symbolic.svg',
                 'io.github.dotfilepilot.App.png'):
        if not (icons / name).is_file() or not (icons / name).stat().st_size:
            raise RuntimeError('Icône absente du paquet installé : ' + name)
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    with tempfile.TemporaryDirectory(prefix='dotfilepilot-installed-') as temp:
        work = Path(temp)
        package = work / 'repo/example'
        package.mkdir(parents=True)
        (package / '.example').write_text('fixture', encoding='utf-8')

        def command(*args):
            return subprocess.run([sys.executable, '-I', '-B', '-m', 'dotfilepilot', *args],
                                  cwd=work, env=environment, text=True, capture_output=True,
                                  timeout=15, check=True).stdout

        console = Path(sys.executable).parent / 'dotfilepilot'
        version = subprocess.run([str(console), '--version'], cwd=work, env=environment,
                                 text=True, capture_output=True, timeout=15, check=True).stdout.strip()
        if version != dotfilepilot.__version__ or command('--version').strip() != version:
            raise RuntimeError('Point d’entrée installé incorrect.')
        if json.loads(command('inventaire', str(work / 'repo'))) != ['example']:
            raise RuntimeError('Inventaire installé incorrect.')
        destination = work / 'clone'
        plan = json.loads(command('cloner', 'https://github.com/example/dotfiles.git', str(destination)))
        if plan['destination'] != str(destination) or destination.exists():
            raise RuntimeError('Le clonage sans --appliquer doit rester un aperçu.')
        command('--help')
    print('Paquet installé vérifié : versions, terminal, inventaire et aperçu sans clonage.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
