# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Check selective baseline reruns using real pytest subprocesses."""

import json

import pytest
import supplemental


@pytest.mark.parametrize('failures', [False, True])
def test_compare_only_failed_cases(tmp_path, monkeypatch, failures):
    suite = tmp_path / 'suite'
    tests = suite / 'tests'
    tests.mkdir(parents=True)
    (tests / 'test_rpath_packages.py').write_text(
        'import os, pytest\n'
        '@pytest.mark.parametrize("package", ["pass", "regression", "existing"])\n'
        'def test_rpath_package(package):\n'
        f'    if not {failures!r}: return\n'
        '    assert package != "existing"\n'
        '    assert package != "regression" or os.environ["MESONPY_RPATH_BACKEND"].endswith("main")\n')
    monkeypatch.setattr(supplemental, 'ROOT', suite)
    output = tmp_path / 'reports'
    assert supplemental.compare(tmp_path / 'pr', tmp_path / 'main', output) == int(failures)
    report = json.loads((output / 'comparison.json').read_text())
    assert len(report['pr']['results']) == 3
    summary = (output / 'summary.md').read_text()
    if failures:
        assert report['main']['results'] == {
            'test_rpath_package[regression]': 'passed',
            'test_rpath_package[existing]': 'failure',
        }
        assert 'PR fails; main passes' in summary
        assert 'Both fail; inspect causes' in summary
    else:
        assert not (output / 'main').exists()
        assert 'no baseline tests were needed' in summary


@pytest.mark.parametrize('code,results', [(2, {'collection': 'error'}), (0, {}),
                                        (0, {'test_rpath_package[skip]': 'skipped'})])
def test_incomplete_run_is_not_success(tmp_path, monkeypatch, code, results):
    calls = []

    def run(backend, output, cases=None):
        calls.append(backend)
        return code, results

    monkeypatch.setattr(supplemental, 'run_backend', run)
    assert supplemental.compare(tmp_path / 'pr', tmp_path / 'main', tmp_path / 'reports') == 1
    assert calls == [tmp_path / 'pr']
