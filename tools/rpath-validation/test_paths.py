# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Keep installed-layout allowances narrower than the header error checks."""

import pytest

from run import check_paths


def plan(build, install=''):
    return {'targets': {'/source/build/module.so': {
        'build_rpaths': build, 'install_rpath': install}}}


def test_translated_install_path(monkeypatch):
    monkeypatch.setattr('sys.platform', 'darwin')
    binaries = {'pkg/module.so': {'paths': ['@loader_path/sub']}}
    assert check_paths(binaries, plan(['@loader_path/sub'], '$ORIGIN/sub'), []) == []


@pytest.mark.parametrize('platform,anchor', [('linux', '$ORIGIN'), ('darwin', '@loader_path')])
@pytest.mark.parametrize('directory', ['', 'pkg/', 'pkg/sub/'])
def test_installed_sibling_is_not_build_only(monkeypatch, platform, anchor, directory):
    monkeypatch.setattr('sys.platform', platform)
    binaries = {directory + 'module.so': {'paths': [anchor]},
                directory + 'library.so': {'paths': []}}
    assert check_paths(binaries, plan([anchor]), []) == []


@pytest.mark.parametrize('platform,anchor', [('linux', '$ORIGIN'), ('darwin', '@loader_path')])
def test_relative_destination_must_contain_another_binary(monkeypatch, platform, anchor):
    monkeypatch.setattr('sys.platform', platform)
    paths = [anchor, anchor + '/../build', anchor + '/../lib']
    binaries = {'pkg/module.so': {'paths': paths}, 'lib/library.so': {'paths': []}}
    errors = check_paths(binaries, plan(paths), [])
    assert errors == [f'pkg/module.so: retained build-only RPATH {p!r}' for p in paths[:2]]


def test_valid_installed_path_does_not_hide_other_errors(monkeypatch):
    monkeypatch.setattr('sys.platform', 'darwin')
    paths = ['@loader_path', '@loader_path', '', 'XXX', '$ORIGIN', '/source/build']
    binaries = {'pkg/module.so': {'paths': paths}, 'pkg/library.so': {'paths': []}}
    errors = check_paths(binaries, plan(['@loader_path']), ['/source'])
    assert errors == [
        "pkg/module.so: duplicate '@loader_path' (2 copies)",
        "pkg/module.so: empty or padding RPATH ''",
        "pkg/module.so: empty or padding RPATH 'XXX'",
        "pkg/module.so: literal macOS $ORIGIN: '$ORIGIN'",
        "pkg/module.so: build/source path '/source/build'",
    ]


def test_measured_toolchain_path_is_preserved(monkeypatch):
    monkeypatch.setattr('sys.platform', 'linux')
    binaries = {'pkg/module.so': {'paths': ['/compiler/lib']}}
    assert check_paths(binaries, plan(['/compiler/lib']), [], ['/compiler/lib']) == []
