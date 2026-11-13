import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts import prepare_linux_build as preparation, stage_desktop


class LinuxPreparationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='dotfilepilot-linux-test-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.version = preparation.project_version()
        self.source = self.root / ('dotfilepilot-' + self.version + '.tar.gz')
        self.source.write_bytes(b'fixture ; aucune extraction ni installation')

    def test_recipes_bind_development_versions_and_verified_sources(self):
        for family in ('debian', 'fedora'):
            with self.subTest(family=family):
                output = self.root / family
                recipes = preparation.prepare(self.source, output, family, '42')
                self.assertEqual((output / self.source.name).read_bytes(), self.source.read_bytes())
                self.assertEqual((output / 'SHA256SUMS').read_text(),
                                 hashlib.sha256(self.source.read_bytes()).hexdigest() + '  ' + self.source.name + '\n')
                files = {path.name: path.read_text() for path in recipes.iterdir()}
                self.assertTrue(files)
                self.assertNotIn('@VERSION@', ''.join(files.values()))
                self.assertNotIn('@RELEASE@', ''.join(files.values()))
                if family == 'debian':
                    self.assertIn('0.1.0~dev0-42', files['changelog'])
                    self.assertTrue((recipes / 'rules').stat().st_mode & 0o100)
                    self.assertIn('gir1.2-gtk-4.0', files['control'])
                else:
                    self.assertIn('Version:        0.1.0~dev0', files['dotfilepilot.spec'])
                    self.assertIn('Release:        42', files['dotfilepilot.spec'])
                    self.assertIn('dotfilepilot-' + self.version, files['dotfilepilot.spec'])

    def test_existing_output_and_bad_inputs_never_overwrite(self):
        output = self.root / 'keep'
        output.mkdir()
        sentinel = output / 'conserver'
        sentinel.write_text('personnel')
        with self.assertRaises(FileExistsError):
            preparation.prepare(self.source, output, 'debian', '1')
        self.assertEqual(list(output.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_text(), 'personnel')
        for family, release in (('debian', '0'), ('fedora', '1\n'), ('fedora', '1;bad'), ('unknown', '1')):
            invalid = self.root / 'invalid'
            with self.subTest(family=family, release=release), self.assertRaises(ValueError):
                preparation.prepare(self.source, invalid, family, release)
            self.assertFalse(invalid.exists())
        with self.assertRaises(ValueError):
            preparation.prepare(self.root / 'wrong.tar.gz', self.root / 'invalid', 'debian', '1')

    def test_desktop_staging_preserves_identity_sizes_and_existing_files(self):
        output = self.root / 'stage'
        stage_desktop.stage(output)
        name = 'io.github.dotfilepilot.App'
        launcher = output / 'usr/share/applications' / (name + '.desktop')
        self.assertIn('Exec=dotfilepilot gui', launcher.read_text())
        self.assertIn('Icon=' + name, launcher.read_text())
        icons = output / 'usr/share/icons/hicolor'
        self.assertEqual(len(list(icons.rglob('*.png'))), 9)
        self.assertEqual(len(list(icons.rglob('*.svg'))), 2)
        original = launcher.read_bytes()
        with self.assertRaises(FileExistsError):
            stage_desktop.stage(output)
        self.assertEqual(launcher.read_bytes(), original)
        with self.assertRaises(ValueError):
            stage_desktop.stage(Path('/'))
        with self.assertRaises(ValueError):
            stage_desktop.stage(stage_desktop.ROOT)
