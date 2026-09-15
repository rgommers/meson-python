# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Build real regression packages; inspect outputs independently of the backend.

MESONPY_RPATH_BACKEND selects a backend checkout for comparisons.
MESONPY_RPATH_REPORT_DIR keeps machine-readable reports and build logs.
"""

import fnmatch
import json
import os
import pathlib
import posixpath
import re
import shutil
import subprocess
import sys
import venv
import zipfile

from collections import Counter

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ROOT / 'tests/packages'
CASES = sorted(path.name for path in PACKAGES.glob('rpath-*') if (path / 'expectations.json').is_file())
CASES.append('sharedlib-in-package-orig')
BACKEND = pathlib.Path(os.environ.get('MESONPY_RPATH_BACKEND', ROOT)).resolve()
PLATFORM = 'linux' if sys.platform.startswith('linux') else sys.platform


def run(args, cwd, env, log):
    result = subprocess.run([os.fspath(arg) for arg in args], cwd=cwd, env=env, capture_output=True, text=True)
    log.append({'command': [os.fspath(arg) for arg in args], 'cwd': os.fspath(cwd),
                'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 0, f'Command failed: {args}\n{result.stdout}\n{result.stderr}'
    return result.stdout


def native(path):
    if not path.is_file():
        return False
    with path.open('rb') as stream:
        header = stream.read(20)
    if header[:4] == b'\x7fELF':
        endian = 'little' if header[5] == 1 else 'big'
        return int.from_bytes(header[16:18], endian) in {2, 3}
    if header[:4] in {b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe'}:
        return int.from_bytes(header[12:16], 'little') in {2, 6, 8}
    if header[:4] in {b'\xfe\xed\xfa\xcf', b'\xfe\xed\xfa\xce'}:
        return int.from_bytes(header[12:16], 'big') in {2, 6, 8}
    return False


def headers(path):
    """Use platform tools, never the RPATH implementation under test."""
    if PLATFORM == 'linux':
        result = subprocess.run(['readelf', '-dW', path], capture_output=True, text=True, check=True)
        tags = re.findall(r'\((RPATH|RUNPATH)\).*?\[(.*)\]', result.stdout)
        return {'tags': [tag for tag, _ in tags],
                'paths': [entry for _, value in tags for entry in value.split(':')], 'raw': result.stdout}
    result = subprocess.run(['otool', '-l', path], capture_output=True, text=True, check=True)
    paths = []
    pending = False
    for line in result.stdout.splitlines():
        line = line.lstrip()
        if line.startswith('cmd '):
            pending = line.split() == ['cmd', 'LC_RPATH']
        elif pending and line.startswith('path '):
            match = re.fullmatch(r'path (.*) \(offset [0-9]+\)', line)
            assert match, f'Unrecognized otool path: {line!r}'
            paths.append(match[1])
            pending = False
    return {'tags': ['LC_RPATH'] * len(paths), 'paths': paths, 'raw': result.stdout}


def inspect(directory):
    return {path.relative_to(directory).as_posix(): headers(path)
            for path in sorted(directory.rglob('*')) if native(path)}


def environment():
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(filter(None, [os.fspath(BACKEND), env.get('PYTHONPATH')]))
    env['PYTHONNOUSERSITE'] = '1'
    return env


def build_input(source, build, env, log):
    # Project configures the same defaults as wheel generation, but this step
    # stops before wheel postprocessing. No RPATH helper is called directly.
    run([sys.executable, '-c',
         'import mesonpy, sys; print(mesonpy.__file__); mesonpy.Project(sys.argv[1], sys.argv[2]).build()',
         source, build], source, env, log)


@pytest.fixture(scope='session')
def rpath_toolchain(tmp_path_factory):
    if PLATFORM not in {'linux', 'darwin'}:
        return []
    temporary = tmp_path_factory.mktemp('rpath-toolchain')
    source = temporary / 'source'
    shutil.copytree(PACKAGES / 'rpath-no-dependencies', source)
    build = temporary / 'build'
    build_input(source, build, environment(), [])
    return next(info['paths'] for name, info in inspect(build).items() if pathlib.Path(name).name.startswith('_probe.'))


def norm(path):
    # Accept Meson's equivalent origin/ and origin spellings, while preserving
    # meaningful spaces. Duplicate detection always examines raw entries first.
    for anchor in ['$ORIGIN', '@loader_path']:
        if path == anchor or path.startswith(anchor + '/'):
            suffix = posixpath.normpath(path[len(anchor):].lstrip('/'))
            return anchor if suffix == '.' else anchor + '/' + suffix
    return posixpath.normpath(path)


def expected_path(value, binary, package, external):
    origin = '@loader_path' if PLATFORM == 'darwin' else '$ORIGIN'
    libdir = f'.{package.replace("-", "_")}.mesonpy.libs'
    relative = posixpath.relpath(libdir, posixpath.dirname(binary))
    return norm(value.replace('{origin}', origin).replace('{libs}', origin + '/' + relative)
                .replace('{external}', external.as_posix()))


def verify(name, binaries, before, spec, package, external, toolchain, meson_version, removal, errors):
    matched = set()
    for rule in spec['rules']:
        targets = [binary for binary in binaries if fnmatch.fnmatchcase(binary, rule['glob'])]
        if not targets:
            errors.append(f'{name}: no binary matched {rule["glob"]}')
        for binary in targets:
            matched.add(binary)
            info = binaries[binary]
            paths = info['paths']
            want = [expected_path(value, binary, package, external) for value in rule['paths']]
            got = [norm(path) for path in paths]
            original = [record for path, record in before.items()
                        if (fnmatch.fnmatchcase(path, rule['input_glob']) if 'input_glob' in rule
                            else pathlib.Path(path).name == pathlib.Path(binary).name)]
            assert len(original) == 1, f'Cannot identify original binary: {binary}'
            old = original[0]
            allowed = set(map(norm, toolchain)) | set(want)
            if meson_version < (1, 9):
                allowed.update(map(norm, old['paths']))
            duplicates = [path for path, count in Counter(paths).items() if count > 1]
            missing = set(want) - set(got)
            unexpected = set(got) - allowed
            lost_toolchain = set(map(norm, toolchain)) & set(map(norm, old['paths'])) - set(got)
            if duplicates or missing or unexpected or lost_toolchain:
                errors.append(f'{name}: {binary}: expected {want!r} plus toolchain {toolchain!r}; actual {paths!r}; '
                              f'duplicates={duplicates!r}, missing={sorted(missing)!r}, '
                              f'unexpected={sorted(unexpected)!r}, lost_toolchain={sorted(lost_toolchain)!r}')
            if any(not path or not path.strip('X') for path in paths):
                errors.append(f'{name}: {binary}: empty or padding RPATH entry {paths!r}')
            if meson_version >= (1, 9):
                unwanted = set(map(norm, removal)) - set(want) - set(map(norm, toolchain))
                if unwanted & set(got):
                    errors.append(f'{name}: {binary}: retained build-only paths {sorted(unwanted & set(got))}')
            if PLATFORM == 'linux':
                tag = rule.get('tag')
                expected_tags = [tag] if tag else old['tags'] if paths else []
                if info['tags'] != expected_tags:
                    errors.append(f'{name}: {binary}: expected tags {expected_tags}, actual {info["tags"]}')
                if rule.get('ordered') and not missing:
                    positions = [got.index(path) for path in want]
                    if positions != sorted(positions):
                        errors.append(f'{name}: {binary}: wrong search precedence: {paths!r}')
    if set(binaries) - matched:
        errors.append(f'{name}: native files missing expectations: {sorted(set(binaries) - matched)}')


@pytest.mark.parametrize('package', CASES, ids=lambda name: name.replace('-', '_'))
def test_rpath_package(package, tmp_path, rpath_toolchain):
    original = package == 'sharedlib-in-package-orig'
    spec = (json.loads((ROOT / 'tests/rpath-original-expectations.json').read_text()) if original else
            json.loads((PACKAGES / package / 'expectations.json').read_text()))
    if PLATFORM not in spec['platforms']:
        pytest.skip(f'{package}: requires {spec["platforms"]}')
    version_string = subprocess.check_output(['meson', '--version'], text=True).strip()
    version = tuple(map(int, version_string.split('.')[:2]))
    if version < tuple(map(int, spec['min_meson'].split('.'))):
        pytest.skip(f'{package}: needs Meson >= {spec["min_meson"]}')
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=BACKEND, capture_output=True, text=True)
    report = {'package': package, 'backend': str(BACKEND), 'backend_commit': revision.stdout.strip(),
              'meson': version, 'meson_version': version_string, 'platform': sys.platform,
              'toolchain_paths': rpath_toolchain, 'logs': [], 'errors': []}
    destination = pathlib.Path(os.environ.get('MESONPY_RPATH_REPORT_DIR', tmp_path / 'reports'))
    destination.mkdir(parents=True, exist_ok=True)
    try:
        source = tmp_path / 'source'
        shutil.copytree(PACKAGES / package, source, ignore=shutil.ignore_patterns('.git', '.mesonpy*', '__pycache__'))
        build = tmp_path / 'build'
        external = tmp_path / 'external'
        env = environment()
        origin = '@loader_path' if PLATFORM == 'darwin' else '$ORIGIN'
        if spec.get('prepare'):
            run([sys.executable, source / 'prepare.py', external], tmp_path, env, report['logs'])
            env['PKG_CONFIG_PATH'] = os.fspath(external / 'lib/pkgconfig')
            report['pkg_config'] = (external / 'lib/pkgconfig/external.pc').read_text()
        if spec.get('ldflags'):
            env['LDFLAGS'] = env.get('LDFLAGS', '') + f' -Wl,-rpath,{origin}/user -Wl,-rpath,{external}'
        build_input(source, build, env, report['logs'])
        before = inspect(build)
        report['input'] = before
        plan = json.loads((build / 'meson-info/intro-install_plan.json').read_text())
        report['install_plan'] = plan
        removal = [path for target in plan.get('targets', {}).values() for path in target.get('build_rpaths', [])]
        if spec.get('input_duplicate'):
            probe = next(info for path, info in before.items() if pathlib.Path(path).name.startswith('_probe.'))
            assert probe['paths'].count(spec['input_duplicate']) == 2, 'Duplicate input was not prepared'
        wheels = tmp_path / 'wheels'
        wheels.mkdir()
        previous = None
        for iteration in range(2):
            run([sys.executable, '-m', 'build', '--wheel', '--no-isolation', '--skip-dependency-check',
                 '-Cbuild-dir=' + str(build),
                 '--outdir', wheels, source], tmp_path, env, report['logs'])
            wheel = next(wheels.glob('*.whl'))
            unpacked = tmp_path / f'wheel-{iteration}'
            with zipfile.ZipFile(wheel) as archive:
                archive.extractall(unpacked)
            binaries = inspect(unpacked)
            report[f'wheel_{iteration}'] = binaries
            if PLATFORM in {'linux', 'darwin'}:
                verify(f'wheel {iteration}', binaries, before, spec, package, external, rpath_toolchain,
                       version, removal, report['errors'])
            snapshot = {path: (info['tags'], info['paths']) for path, info in binaries.items()}
            if previous is not None and snapshot != previous:
                report['errors'].append('Second wheel build changed native path entries or tag types')
            previous = snapshot
        smoke = (ROOT / 'tests/rpath-original-smoke.py').read_text() if original else (source / 'smoke.py').read_text()
        shutil.rmtree(build)
        shutil.rmtree(source)
        environment_dir = tmp_path / 'venv'
        venv.EnvBuilder(with_pip=True).create(environment_dir)
        python = environment_dir / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        for key in ['PYTHONPATH', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH']:
            env.pop(key, None)
        run([python, '-m', 'pip', 'install', '--no-deps', wheel], tmp_path, env, report['logs'])
        try:
            run([python, '-c', smoke], tmp_path, env, report['logs'])
        except AssertionError as error:
            report['errors'].append(str(error))
        assert not report['errors'], '\n\n'.join(report['errors'])
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        (destination / f'{package}.json').write_text(json.dumps(report, indent=2) + '\n')
