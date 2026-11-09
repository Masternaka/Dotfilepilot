"""Exécuter la suite, contrôler les tests ignorés et produire un bilan JSON optionnel."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_SUITES = {
    'test_gtk_integration.': 'DOTFILEPILOT_TEST_GTK',
    'test_deployments.DeploymentTests.test_native_stow': 'DOTFILEPILOT_TEST_STOW',
}


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


def summarize(result, discovered, native_counts, require_native, environ):
    reasons = []
    if not result.wasSuccessful():
        reasons.append('Échec de la suite unittest.')
    if discovered == 0 or result.testsRun != discovered:
        reasons.append('Suite vide ou exécution incomplète.')
    expected_prefixes = tuple(prefix for prefix, flag in OPTIONAL_SUITES.items() if environ.get(flag) != '1')
    unexpected_skips = [test.id() for test, _reason in result.skipped
                        if not test.id().startswith(expected_prefixes)]
    if unexpected_skips:
        reasons.append('Tests ignorés hors des suites natives explicitement désactivées.')
    if require_native:
        if any(native_counts.get(prefix, 0) == 0 for prefix in OPTIONAL_SUITES):
            reasons.append('Une suite native obligatoire est absente.')
        if result.skipped or result.expectedFailures:
            reasons.append('Le contrôle natif exige tous les tests exécutés et réussis.')
    nonpassing = {getattr(test, 'test_case', test).id()
                  for group in (result.failures, result.errors, result.skipped, result.expectedFailures)
                  for test, _detail in group}
    nonpassing.update(test.id() for test in result.unexpectedSuccesses)
    return {
        'schema_version': 1,
        'status': 'failed' if reasons else 'passed',
        'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'python': platform.python_version(),
        'platform': sys.platform,
        'native_required': require_native,
        'discovered': discovered,
        'tests_run': result.testsRun,
        'executed': result.testsRun - len({getattr(test, 'test_case', test).id() for test, _reason in result.skipped}),
        'passed': max(0, result.testsRun - len(nonpassing)),
        'failures': len(result.failures),
        'errors': len(result.errors),
        'expected_failures': len(result.expectedFailures),
        'unexpected_successes': len(result.unexpectedSuccesses),
        'native_discovered': native_counts,
        'skipped': [{'test': test.id(), 'reason': reason} for test, reason in result.skipped],
        'policy_errors': reasons,
    }


def write_report(path, report):
    # Le dossier est préparé explicitement par la CI ; ne jamais remplacer un rapport local existant.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-native', action='store_true', help='Activer GTK/Stow et refuser tout test ignoré.')
    parser.add_argument('--report', type=Path, help='Nouveau fichier JSON dans un dossier existant ; aucun écrasement.')
    args = parser.parse_args(argv)
    if args.require_native:
        for flag in OPTIONAL_SUITES.values():
            os.environ[flag] = '1'
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    identifiers = list(test_ids(suite))
    native_counts = {prefix: sum(identifier.startswith(prefix) for identifier in identifiers)
                     for prefix in OPTIONAL_SUITES}
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = summarize(result, len(identifiers), native_counts, args.require_native, os.environ)
    if args.report is not None:
        try:
            write_report(args.report, report)
        except OSError as error:
            print('Bilan JSON non enregistré : ' + str(error), file=sys.stderr)
            return 1
    for reason in report['policy_errors']:
        print(reason, file=sys.stderr)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
