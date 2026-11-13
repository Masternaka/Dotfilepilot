from contextlib import redirect_stdout
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from dotfilepilot import cli, system
from dotfilepilot.distributions import ADAPTERS
from dotfilepilot.system import PilotError


class DistributionTests(unittest.TestCase):
    def identify(self, content):
        with patch.object(system.platform, 'system', return_value='Linux'), \
                patch.object(Path, 'read_text', return_value=content), \
                patch.object(Path, 'exists', return_value=False):
            return system.distribution()

    def test_families_exact_tokens_and_primary_id(self):
        for content, expected in (
                ('ID=debian\nVERSION_ID="13"', 'debian'),
                ('ID=ubuntu\nID_LIKE=debian', 'debian'),
                ('ID=linuxmint\nID_LIKE="ubuntu debian"', 'debian'),
                ('ID=fedora\nID_LIKE="rhel centos"', 'fedora'),
                ('ID=nobara\nID_LIKE=fedora', 'fedora'),
                ('ID=debian\nID_LIKE=arch', 'debian'),
                ('ID=example\nID_LIKE="other arch debian"', 'arch'),
                ('ID=rhel', None), ('ID=centos\nID_LIKE=rhel', None),
                ('ID=example\nID_LIKE="debianish fedora-remix"', None),
                ('ID=fedora\nVARIANT_ID="broken', None)):
            with self.subTest(content=content):
                result = self.identify(content)
                self.assertEqual(result['famille'], expected)
                self.assertEqual(result['interventions'], expected is not None)

    def test_fedora_atomic_refused_with_variant_or_boot_marker(self):
        for variant in ('silverblue', 'kinoite', 'coreos', 'sway-atomic', 'atomic', 'future-atomic'):
            with self.subTest(variant=variant):
                result = self.identify('ID=fedora\nVARIANT_ID=' + variant)
                self.assertEqual(result['famille'], 'fedora')
                self.assertFalse(result['interventions'])
        with patch.object(system.platform, 'system', return_value='Linux'), \
                patch.object(Path, 'read_text', return_value='ID=fedora\nVARIANT_ID=workstation'), \
                patch.object(Path, 'exists', return_value=True):
            self.assertFalse(system.distribution()['interventions'])

    def test_root_is_refused_for_each_family(self):
        for family in ADAPTERS:
            with self.subTest(family=family), \
                    patch.object(system, 'distribution', return_value={
                        'famille': family, 'interventions': True}), \
                    patch.object(system.os, 'geteuid', return_value=0), self.assertRaises(PilotError):
                system.require_supported()

    def test_manager_presence_does_not_authorize_unknown_system(self):
        with patch.object(system.platform, 'system', return_value='Linux'), \
                patch.object(Path, 'read_text', return_value='ID=unknown'), \
                patch.object(system.shutil, 'which', return_value='/usr/bin/pacman'), \
                patch.object(system, 'run') as run, self.assertRaises(PilotError):
            system.installation_plan()
        run.assert_not_called()

    def test_diagnostic_uses_selected_adapter_without_query(self):
        for family, adapter in ADAPTERS.items():
            with self.subTest(family=family), \
                    patch.object(system, 'distribution', return_value={'famille': family}), \
                    patch.object(system, 'run') as run:
                result = system.diagnostic()
                self.assertEqual(result['gestionnaire'], adapter.manager)
                self.assertEqual(result['paquets_requis'], list(adapter.packages))
                run.assert_not_called()

    def test_native_package_queries_and_plans(self):
        cases = (
            ('arch', 'git\npython\n', ['stow', 'python-gobject', 'gtk4']),
            ('debian', 'git\tii \npython3\thi \nstow\trc \npython3-gi\tiU \n',
             ['stow', 'python3-gi', 'gir1.2-gtk-4.0']),
            ('fedora', 'git\npython3\n', ['stow', 'python3-gobject', 'gtk4']))
        for family, output, missing in cases:
            adapter = ADAPTERS[family]
            identity = {'famille': family, 'id': family, 'interventions': True}
            with self.subTest(family=family), \
                    patch.object(system, 'require_supported', return_value=identity), \
                    patch.object(system.shutil, 'which', return_value='/fixture/tool'), \
                    patch.object(system, 'run', return_value=output) as run:
                plan = system.installation_plan()
                run.assert_called_once_with(list(adapter.query))
                self.assertEqual(plan['distribution'], identity)
                self.assertEqual(plan['manquants'], missing)
                self.assertEqual(plan['commande'], list(adapter.install) + missing)
                self.assertFalse(set(plan['commande']) & {'-y', '--assumeyes', '--noconfirm'})

    def test_dpkg_state_includes_installed_held_but_not_repair_required(self):
        self.assertEqual(ADAPTERS['debian'].installed(
            'git\thi \nstow\tiiR\npython3\tiF \npython3-gi\trc \n'), {'git'})
        with self.assertRaises(ValueError):
            ADAPTERS['debian'].installed('sortie inattendue')
        with patch.object(system, 'require_supported', return_value={'famille': 'debian'}), \
                patch.object(system.shutil, 'which', return_value='/tool'), \
                patch.object(system, 'run', return_value='sortie inattendue'), self.assertRaises(PilotError):
            system.installation_plan()

    def test_missing_manager_query_or_failed_query_blocks_plan(self):
        for family, adapter in ADAPTERS.items():
            with self.subTest(family=family), \
                    patch.object(system, 'require_supported', return_value={'famille': family}):
                for missing in (adapter.manager, adapter.query[0]):
                    with patch.object(system.shutil, 'which', side_effect=lambda name: None if name == missing else '/tool'), \
                            patch.object(system, 'run') as run, self.assertRaises(PilotError):
                        system.installation_plan()
                    run.assert_not_called()
                with patch.object(system.shutil, 'which', return_value='/tool'), \
                        patch.object(system, 'run', side_effect=PilotError('base illisible')), self.assertRaises(PilotError):
                    system.installation_plan()

    def test_install_revalidation_and_postcheck_for_each_manager(self):
        for family, adapter in ADAPTERS.items():
            plan = {'distribution': {'famille': family}, 'manquants': ['stow'],
                    'commande': list(adapter.install) + ['stow']}
            with self.subTest(family=family), patch.object(system, 'require_supported'), \
                    patch.object(system.shutil, 'which', return_value='/sudo'), \
                    patch.object(system, 'installation_plan', side_effect=[plan, {'manquants': []}]), \
                    patch.object(system, 'run') as run:
                system.install(plan)
                run.assert_called_once_with(['sudo'] + plan['commande'], capture=False)
            with patch.object(system, 'require_supported'), \
                    patch.object(system, 'installation_plan', return_value=dict(plan, distribution={'famille': 'unknown'})), \
                    patch.object(system, 'run') as run, self.assertRaises(PilotError):
                system.install(plan)
            run.assert_not_called()

    def test_failed_or_incomplete_install_is_reported(self):
        plan = {'commande': ['dnf', 'install', 'stow'], 'manquants': ['stow']}
        with patch.object(system, 'require_supported'), \
                patch.object(system.shutil, 'which', return_value='/sudo'), \
                patch.object(system, 'installation_plan', return_value=plan), \
                patch.object(system, 'run'), self.assertRaisesRegex(PilotError, 'incomplète'):
            system.install(plan)
        with patch.object(system, 'require_supported'), \
                patch.object(system.shutil, 'which', return_value='/sudo'), \
                patch.object(system, 'installation_plan', return_value=plan), \
                patch.object(system, 'run', side_effect=PilotError('Transaction échouée')), \
                self.assertRaisesRegex(PilotError, 'Transaction'):
            system.install(plan)

    def test_cli_dependencies_preview_does_not_install(self):
        with patch.object(cli, 'installation_plan', return_value={'commande': ['apt-get', 'install', 'stow']}), \
                patch.object(cli, 'install') as install, redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['dependances']), 0)
        install.assert_not_called()
