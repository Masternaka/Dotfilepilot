"""Intégration GTK explicitement activée sous un affichage de test."""

import os
from collections import deque
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('DOTFILEPILOT_TEST_GTK') == '1', 'Intégration GTK désactivée')
class GtkTests(unittest.TestCase):
    @contextmanager
    def preview_scheduler(self):
        """Control worker and idle completion without threads, sleeps or disk writes."""
        workers, callbacks = deque(), deque()

        def thread(*, target, daemon):
            return SimpleNamespace(start=lambda: workers.append(target))

        def idle(callback, *args):
            callbacks.append((callback, args))

        def tick():
            if callbacks:
                callback, args = callbacks.popleft()
                if callback(*args):
                    callbacks.append((callback, args))
            elif workers:
                workers.popleft()()

        def drain():
            for _ in range(1000):
                if not workers and not callbacks:
                    return
                tick()
            self.fail('Préparation non terminée après 1000 étapes simulées')

        with patch('dotfilepilot.gtk_app.Thread', side_effect=thread), \
                patch('dotfilepilot.gtk_app.GLib.idle_add', side_effect=idle):
            yield SimpleNamespace(workers=workers, callbacks=callbacks, tick=tick, drain=drain)

    def complete_preview(self, work):
        with self.preview_scheduler() as scheduler:
            work()
            scheduler.drain()

    @classmethod
    def setUpClass(cls):
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        if not Gtk.init_check():
            raise RuntimeError('Affichage GTK indisponible pour les tests natifs obligatoires.')
        from dotfilepilot.gtk_app import Application
        cls.app = Application()
        if not cls.app.register(None):
            raise RuntimeError('Application GTK non enregistrée.')

    def setUp(self):
        from dotfilepilot.gtk_app import Window
        with patch('dotfilepilot.gtk_app.diagnostic', return_value={'mode': 'test'}):
            self.window = Window(self.app)
        self.addCleanup(self.window.destroy)

    def test_window_and_navigation(self):
        from dotfilepilot.gtk_app import APP_ID
        from gi.repository import Gtk
        self.window.present()
        self.assertEqual(self.window.get_icon_name(), APP_ID)
        theme = Gtk.IconTheme.get_for_display(self.window.get_display())
        self.assertTrue(theme.has_icon(APP_ID))
        self.assertTrue(theme.has_icon(APP_ID + '-symbolic'))
        for name in ('home', 'repo', 'configs', 'history', 'status', 'review'):
            self.window.stack.set_visible_child_name(name)
            self.assertEqual(self.window.stack.get_visible_child_name(), name)
        self.assertFalse(self.window.apply_button.get_sensitive())

    def test_current_state_refresh_only_observes_and_revokes_confirmation(self):
        report = {'observed_at': '2026-11-12T12:00:00+00:00', 'deployments': [],
                  'counts': {}, 'cancelled': 0}
        from dotfilepilot.monitoring import STATES
        report['counts'] = dict.fromkeys(STATES, 0)
        self.window.review({'url': 'https://example.org/repo', 'destination': '/tmp/example'}, lambda: None)
        self.window.agree.set_active(True)
        with patch('dotfilepilot.gtk_app.current_state', return_value=report) as observe, \
                patch('dotfilepilot.gtk_app.deploy.apply') as apply, \
                patch('dotfilepilot.gtk_app.deploy.undo') as undo, \
                patch('dotfilepilot.gtk_app.Thread') as thread, \
                patch('dotfilepilot.gtk_app.GLib.idle_add') as idle:
            self.window.refresh_current_state()
            self.assertIsNone(self.window.pending)
            self.assertFalse(self.window.agree.get_active())
            thread.call_args.kwargs['target']()
            callback, *args = idle.call_args.args
            callback(*args)
        observe.assert_called_once_with()
        apply.assert_not_called()
        undo.assert_not_called()
        self.assertEqual(self.window.stack.get_visible_child_name(), 'status')
        buffer = self.window.status_output.get_buffer()
        self.assertIn('Lecture seule', buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False))
        self.assertFalse(self.window.status_output.get_editable())
        self.assertFalse(self.window.apply_button.get_sensitive())

    def test_current_state_stale_observation_is_discarded(self):
        with patch('dotfilepilot.gtk_app.current_state', return_value={}), \
                patch('dotfilepilot.gtk_app.Thread') as thread, \
                patch('dotfilepilot.gtk_app.GLib.idle_add') as idle, \
                patch.object(self.window, 'show_current_state') as show:
            self.window.refresh_current_state()
            self.window.target.set_text('/tmp/edited-during-observation')
            thread.call_args.kwargs['target']()
            callback, *args = idle.call_args.args
            callback(*args)
        show.assert_not_called()
        self.assertFalse(self.window.busy)

    def test_repository_status_refresh_preserves_confirmation_boundary(self):
        report = {'repository': '/tmp/example-repo', 'branch': 'main', 'revision': 'abc123',
                  'detached': False, 'files': [], 'clean': True, 'external_filters_disabled': False,
                  'observed_at': '2026-11-12T12:00:00+00:00'}
        self.window.repo.set_text(report['repository'])
        self.window.review({'url': 'https://example.org/repo', 'destination': '/tmp/example'}, lambda: None)
        self.window.agree.set_active(True)
        with patch('dotfilepilot.gtk_app.repository_status', return_value=report) as observe, \
                patch('dotfilepilot.gtk_app.Thread') as thread, \
                patch('dotfilepilot.gtk_app.GLib.idle_add') as idle:
            self.window.refresh_repository_status()
            self.assertIsNone(self.window.pending)
            self.assertFalse(self.window.agree.get_active())
            thread.call_args.kwargs['target']()
            callback, *args = idle.call_args.args
            callback(*args)
        observe.assert_called_once_with('/tmp/example-repo')
        self.assertEqual(self.window.stack.get_visible_child_name(), 'repo')
        buffer = self.window.git_output.get_buffer()
        self.assertIn('Branche : main', buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False))
        self.assertFalse(self.window.git_output.get_editable())
        self.assertFalse(self.window.apply_button.get_sensitive())

    def test_repository_status_result_is_discarded_when_repository_changes(self):
        self.window.repo.set_text('/tmp/first-repository')
        with patch('dotfilepilot.gtk_app.repository_status', return_value={}) as observe, \
                patch('dotfilepilot.gtk_app.Thread') as thread, \
                patch('dotfilepilot.gtk_app.GLib.idle_add') as idle, \
                patch.object(self.window, 'show_repository_status') as show:
            self.window.refresh_repository_status()
            self.window.repo.set_text('/tmp/second-repository')
            thread.call_args.kwargs['target']()
            callback, *args = idle.call_args.args
            callback(*args)
        observe.assert_called_once_with('/tmp/first-repository')
        show.assert_not_called()
        self.assertFalse(self.window.busy)

    def test_editing_revokes_confirmation(self):
        self.window.review({'url': 'https://example.org/repo', 'destination': '/tmp/example'}, lambda: None)
        self.window.agree.set_active(True)
        self.window.repo.set_text('/tmp/another-repository')
        self.assertIsNone(self.window.pending)
        self.assertFalse(self.window.agree.get_active())
        self.assertFalse(self.window.apply_button.get_sensitive())

    def history_fixture(self, state='actif', error=None):
        return {'identifier': '20261112T120000Z-abcdef01', 'error': error,
                'date': '2026-11-12 12:00:00 UTC', 'state': state,
                'repository': '/tmp/example-repo', 'target': '/tmp/example-home',
                'packages': ['zsh', 'ghostty']}

    def test_activation_table_filters_keep_global_summary_and_revoke_agreement(self):
        from test_presentation import activation_fixture
        plan = activation_fixture()
        self.complete_preview(lambda: self.window.review(plan, lambda: None))
        self.assertTrue(self.window.activation_panel.get_visible())
        self.assertFalse(self.window.output_scroll.get_visible())
        self.assertEqual(self.window.preview_visible.get_text(), '3 fichier(s) affiché(s) sur 3.')
        summary = self.window.activation_summary.get_text()
        self.assertIn('Liens à créer : 2', summary)
        self.assertIn('sauvegardes prévues : 1', summary)
        for selected in (1, 2, 3, 0):
            self.window.agree.set_active(True)
            self.complete_preview(lambda: self.window.preview_filter.set_selected(selected))
            self.assertFalse(self.window.agree.get_active())
            self.assertEqual(self.window.activation_summary.get_text(), summary)
            self.assertIs(self.window.activation_plan, plan)
            self.assertIsNotNone(self.window.pending)
        self.window.target.set_text('/tmp/another-target')
        self.assertIsNone(self.window.pending)
        self.assertFalse(self.window.apply_button.get_sensitive())

    def test_large_preview_uses_a_model_and_keeps_filter_scope(self):
        from dotfilepilot import gtk_app
        from gi.repository import Gtk
        count = 10000
        plan = {'repository': '/tmp/repo', 'target': '/tmp/target', 'packages': ['zsh'],
                'entries': [{'source': f'/tmp/repo/zsh/.config/item-{index:05}',
                             'target': f'/tmp/target/.config/item-{index:05}',
                             'status': 'nouveau' if index % 2 else 'sauvegarder'}
                            for index in range(count)]}
        with patch('dotfilepilot.gtk_app.label', wraps=gtk_app.label) as create_label:
            self.complete_preview(lambda: self.window.review(plan, lambda: None))
        # Populate the model without eagerly creating one set of cells per file.
        self.assertLess(create_label.call_count, 1000)
        self.assertIsInstance(self.window.preview_table, Gtk.ColumnView)
        self.assertEqual(self.window.preview_model.get_n_items(), count)
        self.assertEqual(self.window.preview_table.get_columns().get_n_items(), 4)
        first = self.window.preview_model.get_item(0)
        self.assertEqual(first.package, 'zsh')
        self.assertEqual(first.target, '/tmp/target/.config/item-00000')
        self.assertEqual(self.window.preview_model.get_item(count - 1).source,
                         '/tmp/repo/zsh/.config/item-09999')
        self.window.agree.set_active(True)
        self.complete_preview(lambda: self.window.preview_filter.set_selected(3))
        self.assertEqual(self.window.preview_model.get_n_items(), count // 2)
        self.assertFalse(self.window.agree.get_active())
        self.assertIs(self.window.activation_plan, plan)
        self.assertIn('10000', self.window.activation_summary.get_text())
        self.complete_preview(lambda: self.window.preview_filter.set_selected(2))
        self.assertEqual(self.window.preview_model.get_n_items(), 0)
        self.assertIn('Aucun fichier', self.window.preview_visible.get_text())
        self.window.review({'state': 'actif', 'records': []}, lambda: None)
        self.assertEqual(self.window.preview_model.get_n_items(), 0)
        self.assertTrue(self.window.output_scroll.get_visible())

    def test_recycled_preview_cell_is_rebound_to_its_current_row(self):
        from dotfilepilot.gtk_app import PreviewRow, bind_preview_cell
        from gi.repository import Gtk
        from unittest.mock import Mock
        cell = Gtk.Label()
        item = Mock()
        item.get_child.return_value = cell
        for package, source in (('zsh', '/tmp/repo/zsh/.zshrc'), ('ghostty', '/tmp/repo/ghostty/.config/config')):
            item.get_item.return_value = PreviewRow(package, {'action': 'Créer le lien',
                                                             'source': source, 'target': '/tmp/target'})
            bind_preview_cell(None, item, 'source')
            self.assertEqual(cell.get_text(), source)

    def test_preview_coalesces_filters_and_cannot_apply_while_preparing(self):
        from dotfilepilot import gtk_app
        from test_presentation import activation_fixture
        action = lambda: self.fail('Application pendant la préparation')
        with self.preview_scheduler() as scheduler, \
                patch('dotfilepilot.gtk_app.activation_table', wraps=gtk_app.activation_table) as prepare:
            self.window.review(activation_fixture(), action)
            self.assertEqual(prepare.call_count, 0)
            self.window.preview_filter.set_selected(1)
            self.window.preview_filter.set_selected(3)
            self.assertEqual(len(scheduler.workers), 1)
            self.assertIsNone(self.window.pending)
            self.assertFalse(self.window.agree.get_sensitive())
            self.assertFalse(self.window.apply_button.get_sensitive())
            self.window.execute()
            scheduler.drain()
        self.assertEqual([call.args[1] for call in prepare.call_args_list], [None, 'sauvegarder'])
        self.assertEqual(self.window.preview_model.get_n_items(), 1)
        self.assertIs(self.window.pending, action)
        self.assertTrue(self.window.agree.get_sensitive())
        self.assertFalse(self.window.agree.get_active())

    def test_preview_batches_stop_when_a_new_filter_is_requested(self):
        plan = {'repository': '/tmp/repo', 'target': '/tmp/target', 'packages': ['zsh'],
                'entries': [{'source': f'/tmp/repo/zsh/.file-{index}',
                             'target': f'/tmp/target/.file-{index}', 'status': 'nouveau'}
                            for index in range(501)]}
        with self.preview_scheduler() as scheduler:
            self.window.review(plan, lambda: None)
            scheduler.tick()  # worker: no GObjects created
            self.assertEqual(self.window.preview_model.get_n_items(), 0)
            scheduler.tick()  # delivery: queue the first GTK batch
            scheduler.tick()  # first batch only
            self.assertEqual(self.window.preview_model.get_n_items(), 200)
            self.assertIsNone(self.window.pending)
            self.assertFalse(self.window.agree.get_sensitive())
            self.window.preview_filter.set_selected(3)
            scheduler.drain()
        self.assertEqual(self.window.preview_model.get_n_items(), 0)
        self.assertIn('Aucun fichier', self.window.preview_visible.get_text())
        self.assertIn('501', self.window.activation_summary.get_text())
        self.assertIsNotNone(self.window.pending)

    def test_preview_field_edit_discards_preparation_and_filter_cannot_restore_action(self):
        from test_presentation import activation_fixture
        with self.preview_scheduler() as scheduler:
            self.window.review(activation_fixture(), lambda: None)
            self.window.target.set_text('/tmp/another-target')
            self.window.preview_filter.set_selected(3)
            scheduler.drain()
        self.assertEqual(self.window.preview_model.get_n_items(), 0)
        self.assertIsNone(self.window.pending)
        self.assertIsNone(self.window.preview_action)
        self.assertFalse(self.window.apply_button.get_sensitive())
        self.assertFalse(self.window.closing())

    def test_old_preparation_cannot_replace_a_new_clone_review(self):
        from test_presentation import activation_fixture
        action = lambda: None
        with self.preview_scheduler() as scheduler:
            self.window.review(activation_fixture(), lambda: None)
            self.window.review({'url': 'https://example.org/repo', 'destination': '/tmp/example'}, action)
            self.window.agree.set_active(True)
            scheduler.drain()
        self.assertIs(self.window.pending, action)
        self.assertTrue(self.window.agree.get_active())
        self.assertTrue(self.window.output_scroll.get_visible())
        self.assertEqual(self.window.preview_model.get_n_items(), 0)

    def test_preview_preparation_error_leaves_application_disabled(self):
        from test_presentation import activation_fixture
        with self.preview_scheduler() as scheduler, \
                patch('dotfilepilot.gtk_app.activation_table', side_effect=ValueError('Erreur simulée')):
            self.window.review(activation_fixture(), lambda: None)
            scheduler.drain()
        self.assertIn('Affichage impossible', self.window.preview_visible.get_text())
        self.assertIsNone(self.window.pending)
        self.assertFalse(self.window.agree.get_sensitive())
        self.assertFalse(self.window.apply_button.get_sensitive())
        self.assertFalse(self.window.closing())

    def test_preview_batch_error_does_not_leave_partial_rows_or_confirmation(self):
        from test_presentation import activation_fixture
        with self.preview_scheduler() as scheduler, \
                patch('dotfilepilot.gtk_app.PreviewRow', side_effect=RuntimeError('Erreur de cellule')):
            self.window.review(activation_fixture(), lambda: None)
            scheduler.drain()
        self.assertIn('Chargement impossible', self.window.preview_visible.get_text())
        self.assertEqual(self.window.preview_model.get_n_items(), 0)
        self.assertIsNone(self.window.pending)
        self.assertFalse(self.window.agree.get_sensitive())
        self.assertFalse(self.window.apply_button.get_sensitive())
        self.assertFalse(self.window.closing())

    def test_filtered_activation_still_applies_the_complete_plan_after_confirmation(self):
        from dotfilepilot import deployments
        from test_presentation import activation_fixture
        plan = activation_fixture()
        with patch('dotfilepilot.gtk_app.deploy.apply', return_value='Terminé') as apply, \
                patch('dotfilepilot.gtk_app.require_arch'), \
                patch('dotfilepilot.gtk_app.Thread') as thread:
            self.complete_preview(lambda: self.window.review(plan, lambda: deployments.apply(plan)))
            self.complete_preview(lambda: self.window.preview_filter.set_selected(3))
            self.window.execute()
            thread.assert_not_called()
            apply.assert_not_called()
            self.window.agree.set_active(True)
            self.window.execute()
            with patch('dotfilepilot.gtk_app.GLib.idle_add') as idle:
                thread.call_args.kwargs['target']()
                callback, *args = idle.call_args.args
                callback(*args)
            apply.assert_called_once_with(plan)
        self.assertFalse(self.window.activation_panel.get_visible())
        self.assertTrue(self.window.output_scroll.get_visible())

    def test_empty_filter_and_other_review_types(self):
        from test_presentation import activation_fixture
        plan = activation_fixture()
        plan['entries'] = plan['entries'][:1]
        self.complete_preview(lambda: self.window.review(plan, lambda: None))
        self.complete_preview(lambda: self.window.preview_filter.set_selected(1))
        self.assertIn('Aucun fichier', self.window.preview_visible.get_text())
        self.assertIn('1 conflit(s)', self.window.activation_summary.get_text())
        for data in ({'url': 'https://example.org/repo', 'destination': '/tmp/example'},
                     {'state': 'actif', 'records': []}):
            self.window.agree.set_active(True)
            self.window.review(data, lambda: None)
            self.assertFalse(self.window.activation_panel.get_visible())
            self.assertTrue(self.window.output_scroll.get_visible())
            self.assertFalse(self.window.agree.get_active())

    def test_history_selection_prepares_preview_without_applying(self):
        entry = self.history_fixture()
        self.window.show_history([entry])
        row = self.window.history_list.get_row_at_index(0)
        self.window.history_list.select_row(row)
        self.assertEqual(self.window.identifier.get_text(), entry['identifier'])
        self.assertTrue(self.window.undo_button.get_sensitive())
        plan = {'state': 'actif', 'records': []}
        with patch('dotfilepilot.gtk_app.deploy.preview_undo', return_value=plan) as preview, \
                patch('dotfilepilot.gtk_app.deploy.undo') as undo, \
                patch.object(self.window, 'task', side_effect=lambda work, done: done(work())):
            self.window.undo_button.emit('clicked')
        preview.assert_called_once_with(entry['identifier'])
        undo.assert_not_called()
        self.assertIsNotNone(self.window.pending)
        self.assertFalse(self.window.agree.get_active())

    def test_history_selection_revokes_confirmation_and_manual_entry_remains_available(self):
        entry = self.history_fixture()
        self.window.show_history([entry])
        self.window.review({'url': 'https://example.org/repo', 'destination': '/tmp/example'}, lambda: None)
        self.window.agree.set_active(True)
        self.window.history_list.select_row(self.window.history_list.get_row_at_index(0))
        self.assertIsNone(self.window.pending)
        self.assertFalse(self.window.agree.get_active())
        self.window.identifier.set_text('20261111T120000Z-abcdef02')
        self.assertIsNone(self.window.history_list.get_selected_row())
        self.assertTrue(self.window.undo_button.get_sensitive())

    def test_history_cancelled_and_damaged_entries_cannot_prepare_undo(self):
        for entry in (self.history_fixture(state='annule'), self.history_fixture(error='Journal illisible')):
            self.window.show_history([entry])
            self.window.history_list.select_row(self.window.history_list.get_row_at_index(0))
            self.assertFalse(self.window.undo_button.get_sensitive())
        self.window.show_history([])
        self.assertEqual(self.window.identifier.get_text(), '')
        self.assertFalse(self.window.undo_button.get_sensitive())
        self.assertEqual(self.window.history_text.get_text(), 'Aucun déploiement.')

    def finish_after_edit(self, action, intervention):
        """Control worker completion without sleeps or real filesystem operations."""
        with patch('dotfilepilot.gtk_app.Thread') as thread, \
                patch('dotfilepilot.gtk_app.GLib.idle_add') as idle, \
                patch('dotfilepilot.gtk_app.require_arch'):
            if intervention:
                self.window.review({'url': 'https://example.org/repo', 'destination': '/tmp/example'}, action)
                self.window.agree.set_active(True)
                self.window.execute()
            else:
                self.window.task(action, lambda result: self.fail('Aperçu obsolète affiché'))
            self.window.repo.set_text('/tmp/edited-during-operation')
            thread.call_args.kwargs['target']()
            callback, *args = idle.call_args.args
            callback(*args)
        buffer = self.window.output.get_buffer()
        self.assertFalse(self.window.busy)
        self.assertIsNone(self.window.pending)
        self.assertFalse(self.window.agree.get_active())
        self.assertFalse(self.window.apply_button.get_sensitive())
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def test_intervention_result_survives_field_edit(self):
        message = self.finish_after_edit(lambda: 'Déploiement terminé : exemple', True)
        self.assertEqual(message, 'Déploiement terminé : exemple')

    def test_intervention_error_survives_field_edit(self):
        def failure():
            raise RuntimeError('Déploiement interrompu : journal exemple')
        message = self.finish_after_edit(failure, True)
        self.assertEqual(message, 'Déploiement interrompu : journal exemple')

    def test_stale_analysis_is_discarded(self):
        message = self.finish_after_edit(lambda: ['zsh'], False)
        self.assertIn('Recommencez l’aperçu', message)
