import copy
import unittest

from dotfilepilot.presentation import activation_table, activation_view
from dotfilepilot.system import PilotError


def activation_fixture():
    return {"repository": "/tmp/dépôt avec espaces", "target": "/tmp/cible",
            "packages": ["zsh-extra", "zsh"],
            "entries": [
                {"source": "/tmp/dépôt avec espaces/zsh/.zshrc", "target": "/tmp/cible/.zshrc",
                 "status": "sauvegarder"},
                {"source": "/tmp/dépôt avec espaces/zsh-extra/.config/zsh/extra",
                 "target": "/tmp/cible/.config/zsh/extra", "status": "actif"},
                {"source": "/tmp/dépôt avec espaces/zsh/.config/zsh/settings",
                 "target": "/tmp/cible/.config/zsh/settings", "status": "nouveau"}]}


class ActivationViewTests(unittest.TestCase):
    def test_table_preparation_produces_ordered_plain_data_without_mutating_plan(self):
        plan = activation_fixture()
        original = copy.deepcopy(plan)
        for status, visible in ((None, 3), ('sauvegarder', 1), ('actif', 1)):
            view = activation_table(plan, status)
            self.assertEqual(len(view['rows']), visible)
            self.assertEqual(view['total'], 3)
            self.assertEqual(view['counts']['sauvegarder'], 1)
            self.assertEqual(view['rows'], [(group['package'], entry)
                                           for group in view['groups'] for entry in group['entries']])
            view['rows'][0][1]['source'] = 'Présentation seulement'
            self.assertEqual(plan, original)

    def test_groups_use_the_exact_package_and_preserve_complete_paths(self):
        view = activation_view(activation_fixture())
        self.assertEqual([group["package"] for group in view["groups"]], ["zsh", "zsh-extra"])
        self.assertEqual([entry["target"] for entry in view["groups"][0]["entries"]],
                         ["/tmp/cible/.config/zsh/settings", "/tmp/cible/.zshrc"])
        self.assertEqual(view["groups"][1]["entries"][0]["source"],
                         "/tmp/dépôt avec espaces/zsh-extra/.config/zsh/extra")
        self.assertEqual(view["counts"], {"nouveau": 1, "actif": 1, "sauvegarder": 1})
        self.assertEqual(view["total"], 3)
        self.assertEqual(view["visible"], 3)

    def test_each_filter_preserves_global_counts_and_the_original_plan(self):
        plan = activation_fixture()
        original = copy.deepcopy(plan)
        for status in ("nouveau", "actif", "sauvegarder"):
            with self.subTest(status=status):
                view = activation_view(plan, status)
                self.assertEqual(view["total"], 3)
                self.assertEqual(view["visible"], 1)
                self.assertEqual(view["counts"], {"nouveau": 1, "actif": 1, "sauvegarder": 1})
                self.assertEqual(view["groups"][0]["entries"][0]["status"], status)
                view["groups"][0]["entries"][0]["target"] = "display only"
                self.assertEqual(plan, original)

    def test_empty_filter_does_not_hide_global_conflicts(self):
        plan = activation_fixture()
        plan["entries"] = plan["entries"][:1]
        view = activation_view(plan, "nouveau")
        self.assertEqual(view["groups"], [])
        self.assertEqual(view["visible"], 0)
        self.assertEqual(view["counts"]["sauvegarder"], 1)
        self.assertEqual(view["total"], 1)

    def test_invalid_filter_is_rejected(self):
        with self.assertRaises(PilotError):
            activation_view(activation_fixture(), "unknown")

    def test_unexpected_source_or_status_is_rejected(self):
        for key, value in (("source", "/tmp/another-repo/zsh/.zshrc"),
                           ("source", "/tmp/dépôt avec espaces/other/.zshrc"), ("status", "unknown")):
            plan = activation_fixture()
            plan["entries"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(PilotError):
                activation_view(plan)
