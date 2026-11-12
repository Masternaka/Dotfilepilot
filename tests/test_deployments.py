import json
import copy
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from dotfilepilot import deployments as d
from dotfilepilot.system import PilotError


def fake_stow(command, cwd=None):
    """Simulates only fixture link creation, never claims native Stow coverage."""
    repository = Path(next(arg[6:] for arg in command if arg.startswith("--dir=")))
    target = Path(next(arg[9:] for arg in command if arg.startswith("--target=")))
    # Match Stow's Getopt::Long callback: '--' ends parsing and later names
    # never reach its package list. The previous fake hid this CLI failure.
    names = []
    for argument in command[1:]:
        if argument == "--":
            break
        if not argument.startswith("-"):
            names.append(argument)
    if not names:
        raise PilotError("stow: No packages to stow or unstow")
    for name in names:
        for source in (repository / name).rglob("*"):
            if not source.is_file() or source.name == "README.md":
                continue
            destination = target / source.relative_to(repository / name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.is_symlink() and destination.resolve() == source:
                continue
            if d.present(destination):
                raise PilotError("Conflit simulé")
            destination.symlink_to(os.path.relpath(source, destination.parent))
    return ""


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "repo"
        self.target = root / "home"
        self.store = root / "state"
        self.target.mkdir()
        self.source = self.repo / "zsh/.config/zsh/settings"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("new")
        self.file = self.target / ".config/zsh/settings"
        self.home = root / "empty-home"
        self.home.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(Path, "home", return_value=self.home).start()
        patch.object(d, "run", side_effect=fake_stow).start()

    def preview(self):
        return d.preview(self.repo, self.target, ["zsh"])

    def existing(self):
        self.file.parent.mkdir(parents=True)
        self.file.write_text("original")
        self.file.chmod(0o640)

    def test_preview_does_not_touch_target(self):
        self.existing()
        plan = self.preview()
        self.assertEqual(plan["entries"][0]["status"], "sauvegarder")
        self.assertEqual(self.file.read_text(), "original")
        self.assertFalse(self.store.exists())

    def test_activate_backup_and_undo(self):
        self.existing()
        identifier = d.apply(self.preview(), self.store)
        self.assertTrue(self.file.is_symlink())
        self.assertEqual(self.file.read_text(), "new")
        self.assertEqual((self.store / identifier / "0.backup").read_text(), "original")
        d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertFalse(self.file.is_symlink())
        self.assertEqual(self.file.read_text(), "original")
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o640)
        self.assertTrue((self.store / identifier / "0.backup").exists())

    def test_original_broken_symlink_is_preserved(self):
        self.file.parent.mkdir(parents=True)
        self.file.symlink_to("missing-original")
        identifier = d.apply(self.preview(), self.store)
        d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertEqual(os.readlink(self.file), "missing-original")

    def test_new_link_removed(self):
        identifier = d.apply(self.preview(), self.store)
        d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertFalse(d.present(self.file))

    def test_multiple_packages_with_spaces_in_paths(self):
        repository = self.repo.parent / "dotfiles with spaces"
        self.repo.rename(repository)
        self.repo = repository
        second = self.repo / "ghostty/.config/ghostty/config"
        second.parent.mkdir(parents=True)
        second.write_text("terminal settings")
        plan = d.preview(self.repo, self.target, ["zsh", "ghostty"])
        self.assertEqual(len(plan["entries"]), 2)
        identifier = d.apply(plan, self.store)
        ghostty = self.target / ".config/ghostty/config"
        self.assertTrue(self.file.is_symlink())
        self.assertEqual(ghostty.read_text(), "terminal settings")
        d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertFalse(d.present(self.file))
        self.assertFalse(d.present(ghostty))

    def test_preexisting_correct_link_is_not_removed(self):
        self.file.parent.mkdir(parents=True)
        self.file.symlink_to(self.source)
        self.assertIn("déjà actives", d.apply(self.preview(), self.store))
        self.assertTrue(self.file.is_symlink())

    def test_stale_source_blocks_before_backup(self):
        self.existing()
        plan = self.preview()
        self.source.write_text("modified")
        with self.assertRaises(PilotError):
            d.apply(plan, self.store)
        self.assertEqual(self.file.read_text(), "original")
        self.assertEqual(d.history(self.store), [])

    def test_stale_target_blocks(self):
        plan = self.preview()
        self.existing()
        with self.assertRaises(PilotError):
            d.apply(plan, self.store)

    def test_external_edit_blocks_undo(self):
        self.existing()
        identifier = d.apply(self.preview(), self.store)
        self.file.unlink()
        self.file.write_text("personal edit")
        with self.assertRaises(PilotError):
            d.preview_undo(identifier, self.store)
        self.assertEqual(self.file.read_text(), "personal edit")

    def test_parent_symlink_blocks(self):
        external = self.target.parent / "external"
        external.mkdir()
        (self.target / ".config").symlink_to(external)
        with self.assertRaises(PilotError):
            self.preview()

    def test_source_symlink_blocks(self):
        self.source.unlink()
        self.source.symlink_to("/etc/passwd")
        with self.assertRaises(PilotError):
            self.preview()

    def test_source_fifo_blocks(self):
        self.source.unlink()
        os.mkfifo(self.source)
        with self.assertRaises(PilotError):
            self.preview()

    def test_implicit_stow_rules_block(self):
        (self.repo / ".stowrc").write_text("--adopt")
        with self.assertRaises(PilotError):
            self.preview()

    def test_package_local_ignore_blocks(self):
        (self.repo / "zsh/.stow-local-ignore").write_text("settings")
        with self.assertRaises(PilotError):
            self.preview()

    def test_non_dotfile_scripts_block(self):
        (self.repo / "zsh/install.sh").write_text("do not run")
        with self.assertRaises(PilotError):
            self.preview()

    def test_invalid_package_blocks(self):
        with self.assertRaises(PilotError):
            d.preview(self.repo, self.target, ["../outside"])

    def test_target_inside_repo_blocks(self):
        with self.assertRaises(PilotError):
            d.preview(self.repo, self.repo / "zsh", ["zsh"])

    def test_interrupted_deployment_can_be_undone(self):
        self.existing()
        plan = self.preview()
        calls = 0

        def fail_real(command, cwd=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PilotError("Stow failed")
            return fake_stow(command, cwd)

        with patch.object(d, "run", side_effect=fail_real):
            with self.assertRaises(PilotError):
                d.apply(plan, self.store)
        identifier = d.history(self.store)[0]
        self.assertFalse(d.present(self.file))
        d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertEqual(self.file.read_text(), "original")

    def test_modified_backup_blocks(self):
        self.existing()
        identifier = d.apply(self.preview(), self.store)
        (self.store / identifier / "0.backup").write_text("corrupt")
        with self.assertRaises(PilotError):
            d.preview_undo(identifier, self.store)

    def test_restored_original_does_not_bypass_backup_validation(self):
        self.existing()
        identifier = d.apply(self.preview(), self.store)
        reviewed = d.preview_undo(identifier, self.store)
        self.file.unlink()
        self.file.write_text("original")
        self.file.chmod(0o640)
        journal = self.store / identifier / "journal.json"
        saved = journal.read_bytes()
        (journal.parent / "0.backup").write_text("corrupt")
        with self.assertRaisesRegex(PilotError, "Sauvegarde modifiée"):
            d.preview_undo(identifier, self.store)
        with self.assertRaisesRegex(PilotError, "Sauvegarde modifiée"):
            d.undo(identifier, reviewed, self.store)
        self.assertEqual(self.file.read_text(), "original")
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o640)
        self.assertEqual(journal.read_bytes(), saved)

    def test_restored_symlink_does_not_bypass_backup_validation(self):
        self.file.parent.mkdir(parents=True)
        self.file.symlink_to("missing-original")
        identifier = d.apply(self.preview(), self.store)
        self.file.unlink()
        self.file.symlink_to("missing-original")
        backup = self.store / identifier / "0.backup"
        backup.unlink()
        backup.symlink_to("changed-backup")
        with self.assertRaisesRegex(PilotError, "Sauvegarde modifiée"):
            d.preview_undo(identifier, self.store)
        self.assertEqual(os.readlink(self.file), "missing-original")

    def test_undo_resumes_after_symlink_restoration_before_journal_save(self):
        self.file.parent.mkdir(parents=True)
        self.file.symlink_to("missing-original")
        identifier = d.apply(self.preview(), self.store)
        journal = self.store / identifier / "journal.json"
        saved = journal.read_bytes()
        reviewed = d.preview_undo(identifier, self.store)
        with patch.object(d, "save", side_effect=OSError("Interruption simulée")):
            with self.assertRaises(OSError):
                d.undo(identifier, reviewed, self.store)
        self.assertEqual(journal.read_bytes(), saved)
        self.assertEqual(os.readlink(self.file), "missing-original")
        original_inode = self.file.lstat().st_ino
        d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertEqual(self.file.lstat().st_ino, original_inode)
        self.assertEqual(os.readlink(self.file), "missing-original")
        self.assertEqual(os.readlink(journal.parent / "0.backup"), "missing-original")
        self.assertEqual(json.loads(journal.read_text())["state"], "annule")

    def test_undo_does_not_recopy_file_restored_before_journal_save(self):
        self.existing()
        identifier = d.apply(self.preview(), self.store)
        reviewed = d.preview_undo(identifier, self.store)
        with patch.object(d, "save", side_effect=OSError("Interruption simulée")):
            with self.assertRaises(OSError):
                d.undo(identifier, reviewed, self.store)
        original = self.file.stat()
        with patch.object(d.shutil, "copy2", side_effect=AssertionError("Original déjà restauré")):
            d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertEqual(self.file.read_text(), "original")
        self.assertEqual(self.file.stat().st_ino, original.st_ino)
        self.assertEqual(self.file.stat().st_mtime_ns, original.st_mtime_ns)
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o640)

    def test_public_state_directory_blocks(self):
        self.store.mkdir(mode=0o755)
        self.store.chmod(0o755)
        with self.assertRaises(PilotError):
            d.apply(self.preview(), self.store)

    def test_identifier_traversal_blocks(self):
        with self.assertRaises(PilotError):
            d.preview_undo("../elsewhere", self.store)

    def test_history_details_include_active_and_cancelled_deployments(self):
        identifier = d.apply(self.preview(), self.store)
        detail = d.history_details(self.store)[0]
        self.assertEqual(detail["identifier"], identifier)
        self.assertEqual(detail["packages"], ["zsh"])
        self.assertEqual(detail["repository"], str(self.repo.resolve()))
        self.assertEqual(detail["target"], str(self.target.resolve()))
        self.assertEqual(detail["state"], "actif")
        self.assertTrue(detail["date"].endswith(" UTC"))
        self.assertIsNone(detail["error"])
        d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertEqual(d.history_details(self.store)[0]["state"], "annule")
        self.assertEqual(d.history(self.store), [identifier])

    def test_history_details_keep_good_entries_when_one_journal_is_damaged(self):
        identifier = d.apply(self.preview(), self.store)
        broken = self.store / "20990101T000000Z-abcdef01"
        broken.mkdir()
        (broken / "journal.json").write_text('{"state":')
        details = d.history_details(self.store)
        self.assertEqual([entry["identifier"] for entry in details], [broken.name, identifier])
        self.assertIn("Journal illisible", details[0]["error"])
        self.assertIsNone(details[1]["error"])
        self.assertTrue(self.file.is_symlink())
        self.assertEqual((broken / "journal.json").read_text(), '{"state":')

    def test_history_details_do_not_require_a_live_target(self):
        identifier = d.apply(self.preview(), self.store)
        self.target.rename(self.target.with_name("moved-home"))
        with patch.object(d, "preview_undo", side_effect=AssertionError("No target inspection")):
            details = d.history_details(self.store)
        self.assertEqual(details[0]["identifier"], identifier)
        self.assertIsNone(details[0]["error"])

    def test_history_details_report_invalid_metadata_and_symbolic_journal(self):
        identifier = d.apply(self.preview(), self.store)
        journal = self.store / identifier / "journal.json"
        original = json.loads(journal.read_text())
        for packages in (None, [12]):
            original["plan"]["packages"] = packages
            journal.write_text(json.dumps(original))
            self.assertIn("Métadonnées", d.history_details(self.store)[0]["error"])
        saved = journal.with_name("saved.json")
        journal.rename(saved)
        journal.symlink_to(saved)
        self.assertIn("symbolique", d.history_details(self.store)[0]["error"])

    def test_history_details_missing_store_is_read_only(self):
        self.assertEqual(d.history_details(self.store), [])
        self.assertFalse(self.store.exists())

    def test_cross_filesystem_backup_blocks_before_any_move(self):
        self.existing()
        second = self.source.parent / "second"
        second.write_text("new second")
        conflict = self.file.parent / "second"
        conflict.write_text("original second")
        plan = self.preview()
        original_lstat = Path.lstat

        def different_device(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            if path == self.file.resolve():
                fields = list(info)
                fields[2] = self.store.stat().st_dev + 1
                return os.stat_result(fields)
            return info

        with patch.object(Path, "lstat", different_device):
            with self.assertRaisesRegex(PilotError, "autre système de fichiers"):
                d.apply(plan, self.store)
        self.assertEqual(self.file.read_text(), "original")
        self.assertEqual(conflict.read_text(), "original second")
        self.assertEqual(d.history(self.store), [])

    def test_invalid_journals_block_without_changing_files(self):
        self.existing()
        identifier = d.apply(self.preview(), self.store)
        journal = self.store / identifier / "journal.json"
        original = json.loads(journal.read_text())
        cases = [[], {}, dict(original, schema_version=2), dict(original, state="unknown"),
                 dict(original, records={}), dict(original, restored=None),
                 dict(original, plan={"target": "relative"})]
        for key, value in (("target", "/tmp/../outside"), ("source", None),
                           ("before", ["fichier"]), ("backup", "../outside")):
            damaged = copy.deepcopy(original)
            damaged["records"][0][key] = value
            cases.append(damaged)
        duplicate = copy.deepcopy(original)
        duplicate["records"].append(copy.deepcopy(duplicate["records"][0]))
        cases.append(duplicate)
        for damaged in cases:
            with self.subTest(journal=damaged):
                journal.write_text(json.dumps(damaged))
                with self.assertRaisesRegex(PilotError, "Journal incomplet"):
                    d.preview_undo(identifier, self.store)
                self.assertTrue(self.file.is_symlink())
                self.assertEqual((journal.parent / "0.backup").read_text(), "original")
                self.assertEqual(json.loads(journal.read_text()), damaged)

    def test_unreadable_journal_reports_recovery_error(self):
        identifier = d.apply(self.preview(), self.store)
        journal = self.store / identifier / "journal.json"
        for content in (b'{"state":', b'\xff'):
            journal.write_bytes(content)
            with self.assertRaisesRegex(PilotError, "Journal illisible"):
                d.preview_undo(identifier, self.store)
            self.assertTrue(self.file.is_symlink())

    def test_legacy_journal_remains_restorable(self):
        self.existing()
        identifier = d.apply(self.preview(), self.store)
        journal = self.store / identifier / "journal.json"
        data = json.loads(journal.read_text())
        del data["schema_version"]
        journal.write_text(json.dumps(data))
        d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
        self.assertEqual(self.file.read_text(), "original")

    @unittest.skipUnless(os.environ.get("DOTFILEPILOT_TEST_STOW") == "1" and shutil.which("stow"),
                         "Intégration Stow réelle explicitement activée et Stow installé requis")
    def test_native_stow(self):
        from dotfilepilot.system import run
        with patch.object(d, "run", side_effect=run):
            self.existing()
            identifier = d.apply(self.preview(), self.store)
            self.assertTrue(self.file.is_symlink())
            d.undo(identifier, d.preview_undo(identifier, self.store), self.store)
            self.assertEqual(self.file.read_text(), "original")
