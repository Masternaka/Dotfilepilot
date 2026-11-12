import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from dotfilepilot import cli, git_status
from dotfilepilot.presentation import repository_status_text
from dotfilepilot.system import PilotError, run


class GitStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve() / 'dépôt avec espaces'
        self.repo.mkdir()
        self.git('init', '--template=')
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main')
        self.file = self.repo / 'config'
        self.file.write_text('fixture\n')

    def git(self, *arguments):
        return run(['git', '-c', 'core.hooksPath=' + os.devnull,
                    '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid']
                   + list(arguments), cwd=self.repo)

    def commit(self):
        self.git('add', '--all')
        self.git('commit', '-m', 'Données fictives')

    def test_unborn_branch_and_untracked_file(self):
        report = git_status.repository_status(self.repo)
        self.assertEqual(report['branch'], 'main')
        self.assertIsNone(report['revision'])
        self.assertFalse(report['detached'])
        self.assertEqual(report['files'][0]['path'], 'config')
        self.assertEqual(report['files'][0]['index'], '?')
        self.assertIn('Aucun commit', repository_status_text(report))

    def test_clean_committed_repository_does_not_rewrite_index_or_head(self):
        self.commit()
        index = self.repo / '.git/index'
        head = self.repo / '.git/HEAD'
        saved = (index.read_bytes(), index.stat().st_mtime_ns, head.read_bytes())
        report = git_status.repository_status(self.repo)
        self.assertTrue(report['clean'])
        self.assertEqual(report['revision'], self.git('rev-parse', 'HEAD').strip())
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns, head.read_bytes()), saved)
        self.assertFalse((self.repo / '.git/index.lock').exists())
        self.assertIn('déplacer ou supprimer', repository_status_text(report))

    def test_added_deleted_modified_and_ignored_paths(self):
        deleted = self.repo / 'deleted'
        deleted.write_text('old')
        (self.repo / '.gitignore').write_text('ignored\n')
        self.commit()
        self.file.write_text('modified fixture\n')
        deleted.unlink()
        (self.repo / 'added').write_text('new')
        self.git('add', 'added')
        unusual = 'non suivi\tavec\naccents é'
        (self.repo / unusual).write_text('new untracked')
        (self.repo / 'ignored').write_text('ignored')
        entries = {entry['path']: entry for entry in git_status.repository_status(self.repo)['files']}
        self.assertEqual(entries['config']['worktree'], 'M')
        self.assertEqual(entries['deleted']['worktree'], 'D')
        self.assertEqual(entries['added']['index'], 'A')
        self.assertIn(unusual, entries)
        self.assertNotIn('ignored', entries)
        text = repository_status_text(git_status.repository_status(self.repo))
        self.assertIn(r'\tavec\n', text)

    def test_detached_head(self):
        self.commit()
        self.git('checkout', '--detach')
        report = git_status.repository_status(self.repo)
        self.assertTrue(report['detached'])
        self.assertIsNone(report['branch'])
        self.assertIsNotNone(report['revision'])
        self.assertIn('Révision détachée', repository_status_text(report))

    def test_non_repository_and_nested_folder_are_rejected(self):
        outside = self.repo.parent / 'outside'
        outside.mkdir()
        nested = self.repo / 'nested'
        nested.mkdir()
        for directory in (outside, nested, self.repo / 'missing'):
            with self.subTest(directory=directory), self.assertRaises(PilotError):
                git_status.repository_status(directory)

    def test_external_filter_and_fsmonitor_are_not_executed(self):
        (self.repo / '.gitattributes').write_text('config filter=trap\n')
        self.commit()
        marker = self.repo.parent / 'must-not-exist'
        script = self.repo.parent / 'external-script'
        script.write_text('#!/bin/sh\nprintf fired > ' + shlex.quote(str(marker)) + '\ncat\n')
        script.chmod(0o700)
        command = shlex.quote(str(script))
        # Included local config exercises the same path as a repository-owned driver.
        included = self.repo / '.git/drivers'
        included.write_text('[filter "trap"]\n\tclean = ' + command
                            + '\n\tprocess = ' + command + '\n\trequired = true\n')
        self.git('config', 'include.path', str(included))
        self.git('config', 'core.fsmonitor', command)
        self.file.write_text('changed fixture that requires comparison\n')
        report = git_status.repository_status(self.repo)
        self.assertFalse(marker.exists())
        self.assertTrue(report['external_filters_disabled'])
        self.assertFalse(report['clean'])
        self.assertIn('neutralisés', repository_status_text(report))

    def test_git_environment_cannot_redirect_the_repository(self):
        self.commit()
        with patch.dict(os.environ, {'GIT_DIR': '/invalid-fixture', 'GIT_WORK_TREE': '/invalid-worktree'}):
            self.assertTrue(git_status.repository_status(self.repo)['clean'])

    def test_reader_blocks_transports_and_optional_locks(self):
        response = subprocess.CompletedProcess([], 0, stdout=b'', stderr=b'')
        with patch.object(git_status.subprocess, 'run', return_value=response) as execute:
            git_status.git_read(self.repo, ['status'])
        args, options = execute.call_args
        self.assertIn('--no-optional-locks', args[0])
        self.assertIn('core.fsmonitor=false', args[0])
        self.assertEqual(options['env']['GIT_ALLOW_PROTOCOL'], '')
        self.assertEqual(options['env']['GIT_OPTIONAL_LOCKS'], '0')
        self.assertFalse(options['shell'])
        self.assertEqual(options['timeout'], 30)

    def test_missing_git_and_timeout_are_explicit_errors(self):
        for error in (FileNotFoundError('git absent'), subprocess.TimeoutExpired(['git'], 30)):
            with patch.object(git_status.subprocess, 'run', side_effect=error), self.assertRaises(PilotError):
                git_status.repository_status(self.repo)

    def test_cli_is_read_only(self):
        self.commit()
        with contextlib.redirect_stdout(io.StringIO()) as output, patch.object(cli, 'confirm') as confirm:
            self.assertEqual(cli.main(['etat-git', str(self.repo)]), 0)
        confirm.assert_not_called()
        self.assertTrue(json.loads(output.getvalue())['clean'])

    def test_conflict_and_rename_records_keep_paths_intact(self):
        output = (b'# branch.oid abcdef\x00# branch.head main\x00'
                  b'u UU N... 100644 100644 100644 100644 abc def ghi conflicted name\x00'
                  b'2 R. N... 100644 100644 100644 abc def R100 new name\x00old name\x00')
        entries = git_status.parse_status(output)['files']
        self.assertTrue(entries[0]['conflict'])
        self.assertEqual(entries[0]['path'], 'conflicted name')
        self.assertEqual(entries[1]['path'], 'new name')
        self.assertEqual(entries[1]['original_path'], 'old name')
