from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dotfilepilot import cli, system
from dotfilepilot.system import PilotError


class SystemTests(unittest.TestCase):
    def test_arch_and_derivatives_are_identified_from_os_release(self):
        for content in ('ID=arch\n', 'ID="arch"\n', "ID='arch'\n",
                        'ID=cachyos\nID_LIKE=arch\n',
                        'ID=endeavouros\nID_LIKE="arch"\n',
                        "ID=manjaro\nID_LIKE='arch linux'\n",
                        '# ID=debian\nID=example\nID_LIKE="other arch"\n'):
            with self.subTest(content=content), \
                    patch.object(system.platform, 'system', return_value='Linux'), \
                    patch.object(Path, 'read_text', return_value=content):
                self.assertTrue(system.is_arch())

    def test_unrelated_or_malformed_distributions_are_rejected(self):
        for content in ('ID=debian\nID_LIKE=ubuntu\n', 'ID=example\nID_LIKE=archlinux\n',
                        'ID=example\nID_LIKE=march\n', '', 'ID="arch\n',
                        'ID=example\nID_LIKE="arch linux\n'):
            with self.subTest(content=content), \
                    patch.object(system.platform, 'system', return_value='Linux'), \
                    patch.object(Path, 'read_text', return_value=content):
                self.assertFalse(system.is_arch())

    def test_non_linux_system_does_not_read_os_release(self):
        with patch.object(system.platform, 'system', return_value='Darwin'), \
                patch.object(Path, 'read_text') as read:
            self.assertFalse(system.is_arch())
        read.assert_not_called()

    def test_os_release_fallback_and_read_errors(self):
        with patch.object(system.platform, 'system', return_value='Linux'):
            with patch.object(Path, 'read_text', side_effect=[FileNotFoundError(), 'ID=arch\n']):
                self.assertTrue(system.is_arch())
            for error in (FileNotFoundError(), PermissionError(), UnicodeError()):
                with self.subTest(error=type(error).__name__), \
                        patch.object(Path, 'read_text', side_effect=error):
                    self.assertFalse(system.is_arch())

    def test_clone_rejects_unsafe_urls(self):
        for url in ("file:///tmp/repo", "ssh://host/repo", "--upload-pack=bad", "https://user:secret@host/repo",
                    "https://host/repo?token=secret", "https://host/repo#fragment"):
            with self.subTest(url=url), self.assertRaises(PilotError):
                system.clone_plan(url, "/tmp/unused")

    def test_existing_clone_destination_blocks(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(PilotError):
            system.clone_plan("https://github.com/example/dotfiles.git", temp)

    def test_clone_preview_has_no_effect(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "clone"
            result = system.clone_plan("https://github.com/example/dotfiles.git", destination)
            self.assertEqual(result["destination"], str(destination))
            self.assertFalse(destination.exists())

    def test_package_probe_failure_does_not_become_missing(self):
        with patch.object(system, "require_arch"), patch.object(system.shutil, "which", return_value="/pacman"), \
                patch.object(system, "run", side_effect=PilotError("database error")):
            with self.assertRaises(PilotError):
                system.installation_plan()

    def test_only_missing_packages_proposed(self):
        with patch.object(system, "require_arch"), patch.object(system.shutil, "which", return_value="/pacman"), \
                patch.object(system, "run", return_value="git\npython\n"):
            plan = system.installation_plan()
            self.assertEqual(plan["manquants"], ["stow", "python-gobject", "gtk4"])
            self.assertNotIn("--noconfirm", plan["commande"])

    def test_install_rechecks_preview(self):
        with patch.object(system, "require_arch"), patch.object(system, "installation_plan", return_value={}), \
                patch.object(system, "run") as execute:
            with self.assertRaises(PilotError):
                system.install({"commande": ["changed"]})
            execute.assert_not_called()

    def test_confirmation_is_not_implicit(self):
        for answer in ("", "oui", "yes", "OUI"):
            with patch("builtins.input", return_value=answer):
                self.assertEqual(cli.confirm(), answer == "OUI")

    def test_cli_preview_never_calls_clone(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(cli, "clone") as execute, redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["cloner", "https://github.com/example/dotfiles.git", temp + "/repo"]), 0)
            execute.assert_not_called()

    def test_non_arch_mutation_blocks(self):
        with patch.object(system, "is_arch", return_value=False), self.assertRaises(PilotError):
            system.require_arch()
