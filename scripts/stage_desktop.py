"""Copier le lanceur et les icônes dans une racine de construction explicite."""

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def stage(destination):
    destination = destination.resolve()
    # Aucune installation directe dans le système ou dans les sources.
    if destination == Path('/') or destination == ROOT or ROOT in destination.parents and not (
            ROOT / 'debian') in destination.parents:
        raise ValueError('Choisir une racine de conditionnement isolée.')
    icons = ROOT / 'dotfilepilot/assets/icons'
    name = 'io.github.dotfilepilot.App'
    files = [(ROOT / 'packaging/arch/dotfilepilot.desktop',
              Path('usr/share/applications') / (name + '.desktop'))]
    for suffix, size in (('.svg', 'scalable'), ('-symbolic.svg', 'symbolic'), ('.png', '512x512')):
        files.append((icons / (name + suffix), Path('usr/share/icons/hicolor') / size / 'apps' / (name + suffix)))
    for size in (16, 24, 32, 48, 64, 128, 256, 1024):
        relative = Path(str(size) + 'x' + str(size)) / 'apps' / (name + '.png')
        files.append((icons / relative.parts[0] / (name + '.png'), Path('usr/share/icons/hicolor') / relative))
    for source, relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Le conditionnement ne doit pas remplacer silencieusement un ancien fichier.
        with target.open('xb') as stream, source.open('rb') as content:
            shutil.copyfileobj(content, stream)
        target.chmod(0o644)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    stage(parser.parse_args().root)
