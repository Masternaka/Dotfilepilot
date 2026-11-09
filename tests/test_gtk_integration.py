"""Intégration GTK explicitement activée sous un affichage de test."""

import os
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get('DOTFILEPILOT_TEST_GTK') == '1', 'Intégration GTK désactivée')
class GtkTests(unittest.TestCase):
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
        self.window.present()
        for name in ('home', 'repo', 'configs', 'history', 'review'):
            self.window.stack.set_visible_child_name(name)
            self.assertEqual(self.window.stack.get_visible_child_name(), name)
        self.assertFalse(self.window.apply_button.get_sensitive())

    def test_editing_revokes_confirmation(self):
        self.window.review({'url': 'https://example.org/repo', 'destination': '/tmp/example'}, lambda: None)
        self.window.agree.set_active(True)
        self.window.repo.set_text('/tmp/another-repository')
        self.assertIsNone(self.window.pending)
        self.assertFalse(self.window.agree.get_active())
        self.assertFalse(self.window.apply_button.get_sensitive())
