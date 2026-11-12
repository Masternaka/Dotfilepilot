import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dotfilepilot import cli, deployments as deploy, monitoring
from dotfilepilot.presentation import current_state_text
from test_deployments import fake_stow


class CurrentStateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / 'repo'
        self.target = self.root / 'home'
        self.store = self.root / 'state'
        self.target.mkdir()
        self.source = self.repo / 'zsh/.zshrc'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('fixture')
        self.link = self.target / '.zshrc'
        self.home = self.root / 'empty-home'
        self.home.mkdir()
        self.patches = [patch.object(Path, 'home', return_value=self.home),
                        patch.object(deploy, 'run', side_effect=fake_stow)]
        for patched in self.patches:
            patched.start()
            self.addCleanup(patched.stop)

    def activate(self):
        return deploy.apply(deploy.preview(self.repo, self.target, ['zsh']), self.store)

    def entry(self):
        return monitoring.current_state(self.store)['deployments'][0]['entries'][0]

    def test_active_link_and_observation_are_read_only(self):
        identifier = self.activate()
        journal = self.store / identifier / 'journal.json'
        saved = journal.read_bytes()
        with patch.object(deploy, 'run', side_effect=AssertionError('Programme interdit')), \
                patch.object(deploy, 'save', side_effect=AssertionError('Écriture interdite')), \
                patch.object(deploy, 'locked', side_effect=AssertionError('Verrou interdit')):
            entry = self.entry()
        self.assertEqual(entry['status'], 'correct')
        self.assertEqual(entry['origin'], 'journalise')
        self.assertEqual(entry['source_state'], 'disponible')
        self.assertEqual(journal.read_bytes(), saved)
        self.assertEqual(self.source.read_text(), 'fixture')
        self.assertTrue(self.link.is_symlink())

    def test_preexisting_link_is_distinguished_from_journalled_intervention(self):
        extra = self.repo / 'zsh/.extra'
        extra.write_text('extra')
        self.link.symlink_to(self.source)
        self.activate()
        entries = monitoring.current_state(self.store)['deployments'][0]['entries']
        by_target = {entry['target']: entry for entry in entries}
        self.assertEqual(by_target[str(self.link)]['origin'], 'preexistant')
        self.assertEqual(by_target[str(self.target / '.extra')]['origin'], 'journalise')
        self.assertTrue(all(entry['status'] == 'correct' for entry in entries))

    def test_moved_repository_reports_broken_link_and_missing_source(self):
        self.activate()
        self.repo.rename(self.root / 'moved-repo')
        entry = self.entry()
        self.assertEqual(entry['status'], 'casse')
        self.assertEqual(entry['source_state'], 'indisponible')
        self.assertIn('Dossier absent', entry['source_error'])

    def test_deleted_source_is_distinguished_from_deleted_link(self):
        self.activate()
        self.source.unlink()
        self.assertEqual(self.entry()['status'], 'casse')
        self.assertEqual(self.entry()['source_state'], 'indisponible')
        self.source.mkdir()
        self.assertEqual(self.entry()['status'], 'indisponible')
        self.source.rmdir()
        self.link.unlink()
        self.assertEqual(self.entry()['status'], 'absent')

    def test_replacements_are_observed_without_reading_their_contents(self):
        self.activate()
        self.link.unlink()
        self.link.write_text('personal change')
        self.assertEqual(self.entry()['status'], 'remplace')
        self.assertEqual(self.link.read_text(), 'personal change')
        self.link.unlink()
        self.link.mkdir()
        self.assertEqual(self.entry()['status'], 'remplace')
        self.link.rmdir()
        other = self.root / 'other'
        other.write_text('external')
        self.link.symlink_to(other)
        self.assertEqual(self.entry()['status'], 'autre_lien')
        self.assertEqual(self.entry()['link'], str(other))

    def test_redirected_root_or_source_parent_is_not_reported_as_correct(self):
        self.activate()
        moved = self.root / 'moved-home'
        self.target.rename(moved)
        self.target.symlink_to(moved)
        self.assertEqual(self.entry()['status'], 'indisponible')
        self.target.unlink()
        moved.rename(self.target)
        source_parent = self.source.parent
        source_parent.rename(self.repo / 'moved-zsh')
        source_parent.symlink_to(self.repo / 'moved-zsh')
        self.assertEqual(self.entry()['source_state'], 'indisponible')
        self.assertNotEqual(self.entry()['status'], 'correct')

    def test_permissions_and_symlink_loops_are_not_treated_as_absence(self):
        self.activate()
        original = monitoring.kind

        def denied(path):
            if path == self.link:
                raise PermissionError('Accès refusé simulé')
            return original(path)

        with patch.object(monitoring, 'kind', side_effect=denied):
            self.assertEqual(self.entry()['status'], 'indisponible')
            self.assertIn('Accès refusé', self.entry()['error'])
        self.link.unlink()
        self.link.symlink_to(self.link.name)
        self.assertEqual(self.entry()['status'], 'indisponible')

    def test_cancelled_deployments_are_not_false_missing_links(self):
        identifier = self.activate()
        deploy.undo(identifier, deploy.preview_undo(identifier, self.store), self.store)
        report = monitoring.current_state(self.store)
        self.assertEqual(report['deployments'], [])
        self.assertEqual(report['cancelled'], 1)
        self.assertEqual(sum(report['counts'].values()), 0)

    def test_observations_remain_separate_for_overlapping_journals(self):
        identifier = self.activate()
        newer = self.store / '20990101T000000Z-abcdef01'
        newer.mkdir()
        (newer / 'journal.json').write_bytes((self.store / identifier / 'journal.json').read_bytes())
        report = monitoring.current_state(self.store)
        self.assertEqual(len(report['deployments']), 2)
        self.assertEqual(report['counts']['correct'], 2)
        self.assertEqual(report['deployments'][0]['entries'][0]['target'],
                         report['deployments'][1]['entries'][0]['target'])

    def test_interrupted_journal_skips_unattempted_and_restored_entries(self):
        self.activate()
        identifier = deploy.history(self.store)[0]
        journal = self.store / identifier / 'journal.json'
        data = json.loads(journal.read_text())
        data['state'] = 'interrompu'
        data['restored'] = data['records']
        data['records'] = []
        data['plan']['entries'].append({'source': str(self.source.parent / '.unattempted'),
                                       'target': str(self.target / '.unattempted'), 'status': 'nouveau'})
        journal.write_text(json.dumps(data))
        report = monitoring.current_state(self.store)
        self.assertEqual(report['deployments'][0]['entries'], [])
        self.assertEqual(sum(report['counts'].values()), 0)

    def test_invalid_journal_does_not_hide_valid_observations(self):
        identifier = self.activate()
        broken = self.store / '20990101T000000Z-abcdef01'
        broken.mkdir()
        (broken / 'journal.json').write_text('{}')
        report = monitoring.current_state(self.store)
        self.assertIsNotNone(report['deployments'][0]['error'])
        self.assertEqual(report['deployments'][1]['identifier'], identifier)
        self.assertEqual(report['counts']['correct'], 1)
        journal = self.store / identifier / 'journal.json'
        data = json.loads(journal.read_text())
        data['plan']['entries'][0]['target'] = str(self.root / 'outside')
        journal.write_text(json.dumps(data))
        with patch.object(monitoring, 'observe', side_effect=AssertionError('Hors périmètre')):
            report = monitoring.current_state(self.store)
        self.assertTrue(all(entry['error'] for entry in report['deployments']))

    def test_empty_state_does_not_create_store_and_cli_exposes_read_only_command(self):
        with patch.object(deploy, 'state_root', return_value=self.store):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.main(['etat']), 0)
        report = json.loads(output.getvalue())
        self.assertFalse(self.store.exists())
        self.assertEqual(report['deployments'], [])
        self.assertIn('Aucun déploiement', current_state_text(report))

    def test_text_report_explains_scope_and_source_errors(self):
        self.activate()
        self.source.unlink()
        text = current_state_text(monitoring.current_state(self.store))
        self.assertIn('Lecture seule', text)
        self.assertIn('Lien cassé', text)
        self.assertIn('Source indisponible', text)
        self.assertIn(str(self.link), text)
        self.assertIn('plusieurs déploiements', text)
