import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare_arch_build.py'
spec = importlib.util.spec_from_file_location('prepare_arch_build', SCRIPT)
preparation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparation)


class ArchPreparationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='dotfilepilot-arch-test-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / ('dotfilepilot-' + preparation.project_version() + '.tar.gz')
        self.source.write_bytes(b'fixture locale ; aucune extraction')
        self.output = self.root / 'build'

    def test_preparation_binds_recipe_to_source_without_changing_it(self):
        original = self.source.read_bytes(), self.source.stat().st_mtime_ns
        with contextlib.redirect_stdout(io.StringIO()):
            recipe = preparation.prepare(self.source, self.output, '42')
        text = recipe.read_text()
        self.assertIn('pkgrel=42\n', text)
        self.assertIn(hashlib.sha256(self.source.read_bytes()).hexdigest(), text)
        self.assertNotIn('@SOURCE_SHA256@', text)
        self.assertNotIn("'SKIP'", text)
        self.assertEqual((self.output / self.source.name).read_bytes(), original[0])
        self.assertEqual((self.source.read_bytes(), self.source.stat().st_mtime_ns), original)

    def test_invalid_revisions_are_rejected_before_creating_output(self):
        for release in ('0', '-1', '01', '1;reboot', '1\n', '1.2'):
            with self.subTest(release=release), self.assertRaises(ValueError):
                preparation.prepare(self.source, self.output, release)
        self.assertFalse(self.output.exists())

    def test_mismatched_source_is_rejected(self):
        wrong = self.root / 'other-1.tar.gz'
        wrong.write_bytes(b'fixture')
        with self.assertRaises(ValueError):
            preparation.prepare(wrong, self.output, '1')
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / 'personal.txt'
        sentinel.write_text('conserver', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            preparation.prepare(self.source, self.output, '1')
        self.assertEqual(sentinel.read_text(), 'conserver')
        self.assertEqual(list(self.output.iterdir()), [sentinel])
