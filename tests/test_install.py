# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

import os
import shutil
import subprocess
import sys

import pytest

import mesonpy

from mesonpy._util import chdir

from .conftest import FREE_THREADED_BUILD, package_dir


# Isolated builds download dependencies and must not run in the offline suite.
pytestmark = pytest.mark.skipif(
    'MESON_PYTHON_CI' not in os.environ,
    reason='requires network access; set MESON_PYTHON_CI to enable',
)


# These packages deliberately exercise invalid input to the backend.
ERRORS = {
    'dist-script': "Program '' not found or not executable",
    'missing-dynamic-version': 'Field "version" declared as dynamic but',
    'missing-meson-version': 'Section "project" missing in pyproject.toml',
    'purelib-platlib-split': 'The purelib-platlib-split package is split',
    'unknown-user-args-meson-args': 'Unknown configuration entry "tool.meson-python.args.unknown"',
    'unknown-user-args-top-level': 'Unknown configuration entry "tool.meson-python.unknown"',
    'unsupported-python-version': '==1.0.0',
    'user-args': 'unrecognized arguments: config-setup',
}


@pytest.fixture(scope='module')
def uv_install(tmp_path_factory):
    uv = shutil.which('uv')
    if uv is None:
        pytest.fail('isolated-install tests require uv on PATH')

    # Constrain isolated builds to this checkout, rather than a released backend.
    dist = tmp_path_factory.mktemp('backend-wheel')
    with chdir(package_dir.parent.parent):
        wheel = dist / mesonpy.build_wheel(dist)
    constraints = dist / 'constraints.txt'
    constraints.write_text(f'meson-python @ {wheel.as_uri()}\n', encoding='utf-8')
    # Some metadata fixtures declare fictitious runtime dependencies. --no-deps
    # excludes those, while still installing all isolated build requirements.
    return [uv, 'pip', 'install', '--no-cache', '--no-deps', '--build-constraints', str(constraints)]


@pytest.mark.parametrize('package', sorted(path.parent.name for path in package_dir.glob('*/pyproject.toml')))
def test_isolated_install(package, uv_install, tmp_path):
    if package == 'cmake-subproject' and sys.platform not in {'linux', 'darwin'}:
        pytest.skip('CMake subproject is not supported on this platform')
    if package == 'library' and sys.platform in {'win32', 'cygwin'}:
        pytest.skip('requires RPATH support')
    if package == 'limited-api-free-threaded' and sys.version_info < (3, 15):
        pytest.skip('requires Python 3.15')
    if package == 'limited-api' and (FREE_THREADED_BUILD or '__pypy__' in sys.builtin_module_names):
        pytest.skip('requires CPython with support for the limited API')

    source = shutil.copytree(
        package_dir / package, tmp_path / package, symlinks=True,
        ignore=shutil.ignore_patterns('.git', '.mesonpy*', 'build', '__pycache__', '*.pyc', '.wraplock'),
    )
    # Separate target environments prevent packages with overlapping module names
    # or build dependencies from affecting one another. uv retains build isolation.
    target = tmp_path / 'venv'
    subprocess.run([uv_install[0], 'venv', '--python', sys.executable, str(target)], check=True)
    python = target / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    result = subprocess.run(
        [*uv_install, '--python', str(python), str(source)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    if package in ERRORS:
        assert result.returncode != 0, result.stdout
        assert ERRORS[package] in ' '.join(result.stdout.split()), result.stdout
    else:
        assert result.returncode == 0, result.stdout
        # Inspect installed metadata without importing fixture-specific modules.
        result = subprocess.run(
            [str(python), '-c',
             'from importlib.metadata import distributions; assert list(distributions())'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        assert result.returncode == 0, result.stdout
