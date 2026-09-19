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
import shutil
import subprocess
import sys
import venv
import zipfile

from collections import Counter

import pytest

from .rpath_inspection import PLATFORM, inspect_binaries, normalize_rpath


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ROOT / 'tests/packages'
CASES = sorted(path.name for path in PACKAGES.glob('rpath-*') if (path / 'expectations.json').is_file())
CASES.append('sharedlib-in-package-orig')
BACKEND = pathlib.Path(os.environ.get('MESONPY_RPATH_BACKEND', ROOT)).resolve()


def run(args, cwd, env, log):
    command = list(map(os.fspath, args))
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    log.append({'command': command, 'cwd': os.fspath(cwd),
                'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 0, f'Command failed: {args}\n{result.stdout}\n{result.stderr}'
    return result.stdout


def environment():
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(filter(None, [os.fspath(BACKEND), env.get('PYTHONPATH')]))
    env['PYTHONNOUSERSITE'] = '1'
    return env


def build_input(source, build, env, log):
    # Project configures the same defaults as wheel generation, but this step
    # stops before wheel postprocessing. No RPATH helper is called directly.
    output = run([sys.executable, '-c',
         'import mesonpy, sys; print(mesonpy.__file__); mesonpy.Project(sys.argv[1], sys.argv[2]).build()',
         source, build], source, env, log)
    imported = pathlib.Path(output.splitlines()[0]).resolve()
    assert imported == BACKEND / 'mesonpy/__init__.py', (
        f'Wrong backend imported: {imported}; expected {BACKEND}. '
        'Use an environment without an overriding editable installation.')


@pytest.fixture(scope='session')
def rpath_toolchain(tmp_path_factory):
    if PLATFORM not in {'linux', 'darwin'}:
        return []
    temporary = tmp_path_factory.mktemp('rpath-toolchain')
    source = temporary / 'source'
    shutil.copytree(PACKAGES / 'rpath-no-dependencies', source)
    build = temporary / 'build'
    build_input(source, build, environment(), [])
    return next(info['paths'] for name, info in inspect_binaries(build).items()
                if pathlib.Path(name).name.startswith('_probe.'))


def expected_path(value, binary, package, external):
    origin = '@loader_path' if PLATFORM == 'darwin' else '$ORIGIN'
    libdir = f'.{package.replace("-", "_")}.mesonpy.libs'
    relative = posixpath.relpath(libdir, posixpath.dirname(binary))
    return normalize_rpath(value.replace('{origin}', origin).replace('{libs}', origin + '/' + relative)
                .replace('{external}', external.as_posix()))


def verify(name, binaries, before, spec, package, external, toolchain, meson_version, removal, errors):
    matched = set()
    toolchain_paths = set(map(normalize_rpath, toolchain))
    build_paths = set(map(normalize_rpath, removal))
    for rule in spec['rules']:
        targets = [binary for binary in binaries if fnmatch.fnmatchcase(binary, rule['glob'])]
        if not targets:
            errors.append(f'{name}: no binary matched {rule["glob"]}')
        for binary in targets:
            matched.add(binary)
            info = binaries[binary]
            if 'elf_paths' in rule:
                # Dual-tag fixtures have exact, independently prepared inputs.
                # An empty RUNPATH is intentional: removing it activates RPATH.
                expected = {tag: [expected_path(path, binary, package, external) for path in paths]
                            for tag, paths in rule['elf_paths'].items()}
                error = compare_elf_paths(info, expected, rule.get('optional_elf_tags', []))
                if error:
                    errors.append(f'{name}: {binary}: {error}')
                continue
            paths = info['paths']
            want = [expected_path(value, binary, package, external) for value in rule['paths']]
            got = [normalize_rpath(path) for path in paths]
            if 'input_glob' in rule:
                original = [record for path, record in before.items() if fnmatch.fnmatchcase(path, rule['input_glob'])]
            else:
                original = [record for path, record in before.items() if pathlib.Path(path).name == pathlib.Path(binary).name]
            assert len(original) == 1, f'Cannot identify original binary: {binary}'
            old = original[0]
            wanted_paths, actual_paths = set(want), set(got)
            old_paths = set(map(normalize_rpath, old['paths']))
            allowed = toolchain_paths | wanted_paths
            if meson_version < (1, 9):
                allowed.update(old_paths)
            duplicates = [path for path, count in Counter(paths).items() if count > 1]
            missing = wanted_paths - actual_paths
            unexpected = actual_paths - allowed
            lost_toolchain = (toolchain_paths & old_paths) - actual_paths
            if duplicates or missing or unexpected or lost_toolchain:
                errors.append(f'{name}: {binary}: expected {want!r} plus toolchain {toolchain!r}; actual {paths!r}; '
                              f'duplicates={duplicates!r}, missing={sorted(missing)!r}, '
                              f'unexpected={sorted(unexpected)!r}, lost_toolchain={sorted(lost_toolchain)!r}')
            if any(not path or not path.strip('X') for path in paths):
                errors.append(f'{name}: {binary}: empty or padding RPATH entry {paths!r}')
            if meson_version >= (1, 9):
                retained_build_paths = actual_paths & (build_paths - wanted_paths - toolchain_paths)
                if retained_build_paths:
                    errors.append(f'{name}: {binary}: retained build-only paths {sorted(retained_build_paths)}')
            if PLATFORM == 'linux':
                expected_tags = old['tags'] if paths else []
                if 'tag' in rule:
                    expected_tags = [rule['tag']]
                if info['tags'] != expected_tags:
                    errors.append(f'{name}: {binary}: expected tags {expected_tags}, actual {info["tags"]}')
                if rule.get('ordered') and not missing:
                    positions = [got.index(path) for path in want]
                    if positions != sorted(positions):
                        errors.append(f'{name}: {binary}: wrong search precedence: {paths!r}')
    if set(binaries) - matched:
        errors.append(f'{name}: native files missing expectations: {sorted(set(binaries) - matched)}')


def compare_elf_paths(info, expected, optional=()):
    actual = {tag: [normalize_rpath(path) for path in paths]
              for tag, paths in info['paths_by_tag'].items()}
    expected = {tag: paths for tag, paths in expected.items() if tag not in optional or tag in actual}
    if actual != expected or Counter(info['tags']) != Counter(expected.keys()):
        return f'expected ELF paths {expected!r}, actual {actual!r}, tags {info["tags"]!r}'
    return None


@pytest.mark.parametrize('package', CASES, ids=lambda name: name.replace('-', '_'))
def test_rpath_package(package, tmp_path, rpath_toolchain):
    original = package == 'sharedlib-in-package-orig'
    expectations = ROOT / 'tests/rpath-original-expectations.json' if original else PACKAGES / package / 'expectations.json'
    spec = json.loads(expectations.read_text())
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
        # Capture the linked input before wheel postprocessing.
        build_input(source, build, env, report['logs'])
        before = inspect_binaries(build)
        report['input'] = before
        for pattern, expected in spec.get('input_elf_paths', {}).items():
            inputs = [info for path, info in before.items() if fnmatch.fnmatchcase(path, pattern)]
            assert len(inputs) == 1, f'Expected one input matching {pattern}'
            expected = {tag: [expected_path(path, pattern, package, external) for path in paths]
                        for tag, paths in expected.items()}
            assert compare_elf_paths(inputs[0], expected) is None, f'Dual-tag input was not prepared: {inputs[0]}'
        for pattern, tags in spec.get('input_tags', {}).items():
            inputs = [info for path, info in before.items() if fnmatch.fnmatchcase(path, pattern)]
            assert len(inputs) == 1 and inputs[0]['tags'] == tags, f'Unexpected input tags for {pattern}: {inputs}'
        plan = json.loads((build / 'meson-info/intro-install_plan.json').read_text())
        report['install_plan'] = plan
        removal = [path for target in plan.get('targets', {}).values() for path in target.get('build_rpaths', [])]
        if spec.get('input_duplicate'):
            probe = next(info for path, info in before.items() if pathlib.Path(path).name.startswith('_probe.'))
            assert probe['paths'].count(spec['input_duplicate']) == 2, 'Duplicate input was not prepared'
        wheels = tmp_path / 'wheels'
        wheels.mkdir()
        # A reused build directory must produce the same paths on both runs.
        previous = None
        for iteration in range(2):
            run([sys.executable, '-m', 'build', '--wheel', '--no-isolation', '--skip-dependency-check',
                 '-Cbuild-dir=' + str(build),
                 '--outdir', wheels, source], tmp_path, env, report['logs'])
            wheel = next(wheels.glob('*.whl'))
            unpacked = tmp_path / f'wheel-{iteration}'
            with zipfile.ZipFile(wheel) as archive:
                archive.extractall(unpacked)
            binaries = inspect_binaries(unpacked)
            report[f'wheel_{iteration}'] = binaries
            if PLATFORM in {'linux', 'darwin'}:
                verify(f'wheel {iteration}', binaries, before, spec, package, external, rpath_toolchain,
                       version, removal, report['errors'])
            snapshot = {path: (info['tags'], info['paths'], info.get('paths_by_tag')) for path, info in binaries.items()}
            if previous is not None and snapshot != previous:
                report['errors'].append('Second wheel build changed native path entries or tag types')
            previous = snapshot
        # Exercise the installed native code after removing build products.
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
