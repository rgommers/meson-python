# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Inspect a native wheel and smoke-test it outside its build environment.

Run with the Python used to build the wheel, after installing its runtime
dependencies. The temporary installation inherits those dependencies, but
the wheel itself is installed into a fresh virtual environment.
"""

import argparse
import hashlib
import json
import os
import pathlib
import site
import subprocess
import sys
import tempfile
import venv
import zipfile

from collections import Counter


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, os.fspath(ROOT))

import mesonpy  # noqa: E402

from mesonpy._rpath import _ELF, _MacOS  # noqa: E402


def output(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=pathlib.Path)
    parser.add_argument('--smoke', required=True, help='Python code exercising the installed native dependencies')
    parser.add_argument('--source', type=pathlib.Path, help='Downstream checkout, for recording its revision')
    parser.add_argument('--forbid', action='append', default=[], help='RPATH substring which must be absent (repeatable)')
    parser.add_argument('--report', type=pathlib.Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    report = {
        'wheel': str(wheel),
        'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
        'python': sys.version,
        'platform': sys.platform,
        'meson': output('meson', '--version'),
        'backend_commit': output('git', 'rev-parse', 'HEAD', cwd=ROOT),
        'backend_diff': output('git', 'diff', 'HEAD', '--', 'mesonpy', cwd=ROOT),
        'source_commit': output('git', 'rev-parse', 'HEAD', cwd=args.source) if args.source else None,
        'source_diff': output('git', 'diff', 'HEAD', cwd=args.source) if args.source else None,
        'binaries': {},
        'errors': [],
    }
    if sys.platform == 'darwin':
        report['os_version'] = output('sw_vers')
        report['xcode'] = output('xcodebuild', '-version')
    elif sys.platform.startswith('linux'):
        report['patchelf'] = output('patchelf', '--version')
    else:
        parser.error('run this check on Linux or macOS')

    with tempfile.TemporaryDirectory(prefix='mesonpy-wheel-rpaths-') as temporary:
        tmp = pathlib.Path(temporary)
        unpacked = tmp / 'unpacked'
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(unpacked)
        for binary in sorted(unpacked.rglob('*')):
            if not binary.is_file() or not mesonpy._is_native(binary):
                continue
            name = binary.relative_to(unpacked).as_posix()
            try:
                if sys.platform == 'darwin':
                    paths = _MacOS._get_rpaths(binary, all_archs=True)
                    kind = 'LC_RPATH'
                else:
                    paths = {'native': _ELF.get_rpath(binary)}
                    kind = 'DT_RPATH' if _ELF._has_rpath(binary) else 'DT_RUNPATH or absent'
                report['binaries'][name] = {'kind': kind, 'paths': paths}
                for arch, entries in paths.items():
                    duplicates = [path for path, count in Counter(entries).items() if count > 1]
                    if duplicates:
                        report['errors'].append(f'{name} [{arch}]: duplicate paths {duplicates}')
                    for path in entries:
                        if any(part in path for part in args.forbid):
                            report['errors'].append(f'{name} [{arch}]: forbidden path {path}')
                        if sys.platform == 'darwin' and '$ORIGIN' in path:
                            report['errors'].append(f'{name} [{arch}]: literal $ORIGIN: {path}')
            except (OSError, ValueError, subprocess.CalledProcessError) as error:
                report['errors'].append(f'{name}: inspection failed: {error}')

        environment = tmp / 'venv'
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
        python = environment / 'bin/python'
        env = os.environ.copy()
        for key in ['PYTHONPATH', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH']:
            env.pop(key, None)
        env['PYTHONNOUSERSITE'] = '1'
        # A venv made from another venv inherits only the base interpreter's
        # packages. Append the calling environment's dependency locations too,
        # after the fresh environment's own site-packages (and installed wheel).
        site_directory = pathlib.Path(subprocess.check_output(
            [python, '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'], env=env, text=True).strip())
        (site_directory / '_rpath_check_dependencies.pth').write_text('\n'.join(site.getsitepackages()) + '\n')
        installed = subprocess.run([python, '-m', 'pip', 'install', '--no-deps', '--force-reinstall', wheel],
                                   cwd=tmp, env=env, capture_output=True, text=True)
        report['installation'] = {'returncode': installed.returncode, 'stdout': installed.stdout, 'stderr': installed.stderr}
        if installed.returncode:
            report['errors'].append('wheel installation failed')
        else:
            result = subprocess.run([python, '-c', args.smoke], cwd=tmp, env=env, capture_output=True, text=True)
            report['smoke'] = {'code': args.smoke, 'returncode': result.returncode,
                               'stdout': result.stdout, 'stderr': result.stderr}
            if result.returncode:
                report['errors'].append('installed-wheel smoke test failed')

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(report["binaries"])} binaries inspected; {len(report["errors"])} errors; report: {args.report}')
    return bool(report['errors'])


if __name__ == '__main__':
    sys.exit(main())
