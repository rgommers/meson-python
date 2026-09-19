# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Run the PR once, then compare only failing packages against main."""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[2]
TEST = 'tests/test_rpath_packages.py'


def read_results(path):
    if not path.exists():
        return {}
    results = {}
    for case in ET.parse(path).iter('testcase'):
        status = next((tag for tag in ('error', 'failure', 'skipped')
                       if case.find(tag) is not None), 'passed')
        results[case.attrib['name']] = status
    return results


def run_backend(backend, output, cases=None):
    output.mkdir(parents=True)
    env = dict(os.environ, MESONPY_RPATH_BACKEND=str(backend),
               MESONPY_RPATH_REPORT_DIR=str(output), PYTHONUNBUFFERED='1')
    env.pop('PYTHONPATH', None)
    selected = [f'{TEST}::{case}' for case in cases] if cases else [TEST]
    # Keep venvs and intermediate builds out of the uploaded report directory.
    with tempfile.TemporaryDirectory(prefix='rpath-supplemental-') as temporary:
        command = [sys.executable, '-m', 'pytest', *selected, '-vv', '--tb=short',
                   '--junitxml=' + str(output / 'junit.xml'), '--basetemp=' + temporary]
        (output / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
        result = subprocess.run(command, cwd=ROOT, env=env)
    return result.returncode, read_results(output / 'junit.xml')


def compare(backend, baseline, output):
    output.mkdir(parents=True)
    pr_code, pr = run_backend(backend, output / 'pr')
    failed = [name for name, status in pr.items() if status in ('failure', 'error')]
    # Collection/interpreter failures are not package outcomes to compare.
    cases = [name for name in failed if name.startswith('test_rpath_package[')]
    main_code, main = None, {}
    if pr_code == 1 and cases:
        main_code, main = run_backend(baseline, output / 'main', cases)

    lines = ['# Supplemental RPATH comparison', '',
             f'PR checkout: `{backend}`; main checkout: `{baseline}`.', '',
             f'PR pytest exit: `{pr_code}`; main pytest exit: `{main_code}`.', '']
    if cases:
        lines += ['| Package | PR | main | Interpretation |', '| --- | --- | --- | --- |']
        for name in cases:
            other = main.get(name, 'not run')
            if other == 'passed':
                interpretation = 'PR fails; main passes'
            elif other in ('failure', 'error'):
                interpretation = 'Both fail; inspect causes'
            else:
                interpretation = 'Baseline comparison inconclusive'
            lines.append(f'| `{name}` | {pr[name]} | {other} | {interpretation} |')
    elif pr_code == 0 and 'passed' in pr.values():
        lines.append('PR passed; no baseline tests were needed.')
    else:
        lines.append('No usable passing PR run; inspect pytest output for infrastructure/collection errors.')
    lines += ['', 'Baseline failures do not automatically excuse PR failures. '
              'Compare the per-package JSON reports and JUnit diagnostics.', '']
    (output / 'summary.md').write_text('\n'.join(lines))
    (output / 'comparison.json').write_text(json.dumps({
        'pr': {'exit_code': pr_code, 'results': pr},
        'main': {'exit_code': main_code, 'results': main},
    }, indent=2) + '\n')
    # Keep failures visible even when main fails too: their causes may differ.
    return int(pr_code != 0 or not pr or 'passed' not in pr.values() or bool(failed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', required=True, type=pathlib.Path)
    parser.add_argument('--baseline', required=True, type=pathlib.Path)
    parser.add_argument('--output', required=True, type=pathlib.Path)
    args = parser.parse_args()
    return compare(args.backend.resolve(), args.baseline.resolve(), args.output.resolve())


if __name__ == '__main__':
    sys.exit(main())
