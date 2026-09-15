# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""One-time downstream builds. Every command and failure is retained in artifacts."""

import argparse
import hashlib
import json
import os
import pathlib
import shlex
import shutil
import signal
import sys
import time
import zipfile

from collections import Counter

import tomllib

from commands import stream_command


ROOT = pathlib.Path(__file__).resolve().parents[2]
# Make the checkout's shared, standard-library-only inspector importable.
sys.path.insert(0, str(ROOT))

from tests.rpath_inspection import inspect_binaries, normalize_rpath  # noqa: E402


def check_paths(binaries, install_plan, forbidden_prefixes, toolchain_paths=()):
    """Return all header problems without stopping the installed-wheel test."""
    failures = []
    toolchain_paths = set(map(normalize_rpath, toolchain_paths))
    for name, info in binaries.items():
        targets = [target for filename, target in install_plan.get('targets', {}).items()
                   if pathlib.Path(filename).name == pathlib.Path(name).name]
        build_paths = {normalize_rpath(path) for target in targets for path in target.get('build_rpaths', [])}
        install_paths = {normalize_rpath(path) for target in targets
                         for path in (target.get('install_rpath') or '').split(':') if path}
        for path, count in Counter(info['paths']).items():
            if not path or not path.strip('X'):
                failures.append(f'{name}: empty or padding RPATH {path!r}')
            if normalize_rpath(path) in build_paths - install_paths - toolchain_paths:
                failures.append(f'{name}: retained build-only RPATH {path!r}')
            if count > 1:
                failures.append(f'{name}: duplicate {path!r} ({count} copies)')
            if any(str(prefix) in path for prefix in forbidden_prefixes):
                failures.append(f'{name}: build/source path {path!r}')
            if sys.platform == 'darwin' and '$ORIGIN' in path:
                failures.append(f'{name}: literal macOS $ORIGIN: {path!r}')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', choices=['numpy', 'gridfire', 'vapoursynth', 'dwave-optimization'])
    parser.add_argument('--backend', required=True, type=pathlib.Path)
    parser.add_argument('--output', required=True, type=pathlib.Path)
    parser.add_argument('--repair', action='store_true')
    parser.add_argument('--lock', type=pathlib.Path, help='Create once, then reuse build/runtime dependency constraints')
    parser.add_argument('--timeout', type=int, default=1500, help='Total backend budget in seconds (default: 1500)')
    parser.add_argument('--command-timeout', type=int, default=300, help='Ordinary command limit in seconds (default: 300)')
    parser.add_argument('--build-timeout', type=int, default=1200, help='Wheel build limit in seconds (default: 1200)')
    parser.add_argument('--jobs', type=int, default=2, help='Parallel compilation jobs (default: 2)')
    args = parser.parse_args()
    if min(args.timeout, args.command_timeout, args.build_timeout, args.jobs) <= 0:
        parser.error('timeouts and jobs must be positive')
    deadline = time.monotonic() + args.timeout

    def cancelled(signum, frame):
        raise KeyboardInterrupt('Runner cancelled by SIGTERM')

    signal.signal(signal.SIGTERM, cancelled)
    config = json.loads((pathlib.Path(__file__).parent / 'projects.json').read_text())[args.project]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = output / 'source'
    backend = args.backend.resolve()
    report = {'project': args.project, 'configuration': config, 'commands': [], 'errors': []}
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env['PYTHONUNBUFFERED'] = '1'
    env['GIT_TERMINAL_PROMPT'] = '0'
    logs = output / 'logs'
    logs.mkdir()

    def save_report():
        for name, data in [('commands.json', report['commands']), ('report.json', report)]:
            path = output / name
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, indent=2) + '\n')
            temporary.replace(path)

    def run(command, cwd=output, check=True, timeout=None):
        command = list(map(str, command))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f'Backend exceeded its {args.timeout}s budget')
        limit = min(timeout or args.command_timeout, remaining)
        log_prefix = logs / f'{len(report["commands"]):03d}'
        record = {'command': command, 'cwd': str(cwd), 'state': 'running', 'timeout_seconds': limit,
                  'stdout_log': str(log_prefix.with_suffix('.stdout.log').relative_to(output)),
                  'stderr_log': str(log_prefix.with_suffix('.stderr.log').relative_to(output))}
        report['commands'].append(record)
        save_report()
        print(f'>>> {shlex.join(command)} (limit {limit:.0f}s; cwd {cwd})', flush=True)
        started = time.monotonic()
        try:
            result, timed_out = stream_command(command, cwd, env, log_prefix, limit)
            record.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                          state='timed_out' if timed_out else 'finished')
        except BaseException as error:
            record['state'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
            raise
        finally:
            record['elapsed_seconds'] = time.monotonic() - started
            save_report()
        status = 'timeout' if timed_out else result.returncode
        print(f'[{status}] {shlex.join(command)}', flush=True)
        if timed_out:
            raise RuntimeError(f'Command exceeded {limit:.0f}s: {shlex.join(command)}')
        if check and result.returncode:
            raise RuntimeError(f'Command failed (exit {result.returncode}): {shlex.join(command)}')
        return result

    try:
        # Check out the pinned project and record the native toolchain.
        run(['git', 'init', source])
        run(['git', 'remote', 'add', 'origin', config['repository']], cwd=source)
        run(['git', 'fetch', '--depth=1', 'origin', config['revision']], cwd=source)
        run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=source)
        run(['git', 'submodule', 'update', '--init', '--recursive', '--depth=1'], cwd=source)
        report['submodules'] = run(['git', 'submodule', 'status', '--recursive'], cwd=source).stdout
        report['backend_commit'] = run(['git', 'rev-parse', 'HEAD'], cwd=backend).stdout.strip()
        report['compiler'] = run([*shlex.split(env.get('CC', 'cc')), '--version']).stdout
        # Resolve dependencies once, then reuse their constraints across backends.
        build_environment = output / 'build-env'
        run([sys.executable, '-m', 'venv', build_environment])
        python = build_environment / 'bin/python'
        requirements = tomllib.loads((source / 'pyproject.toml').read_text())['build-system']['requires']
        # Deliberately substitute the backend checkout. Keep all other upstream
        # requirements, including their minimum Meson and Cython versions.
        requirements = [item for item in requirements if not item.lower().startswith('meson-python')]
        report['backend_requirement_override'] = True
        constraints = ['-c', str(args.lock.resolve())] if args.lock and args.lock.exists() else []
        run([python, '-m', 'pip', 'install', *constraints, 'build', 'ninja', 'pytest', 'hypothesis',
             'pyproject-metadata>=0.9', 'meson',
             *(['patchelf'] if sys.platform.startswith('linux') else []), *requirements, *config['runtime']])
        run([python, '-m', 'pip', 'install', '--no-build-isolation', '--no-deps', backend])
        env['PATH'] = str(build_environment / 'bin') + os.pathsep + env['PATH']
        if args.project == 'numpy':
            pc = source / '.openblas'
            pc.mkdir(exist_ok=True)
            result = run([python, '-c', 'import scipy_openblas64 as ob; print(ob.get_pkg_config(use_preloading=False))'])
            (pc / 'scipy-openblas.pc').write_text(result.stdout)
            report['pkg_config'] = result.stdout
            env['PKG_CONFIG_PATH'] = str(pc)
        if args.project == 'gridfire':
            # The pinned liblogging subproject omits its pthread dependency.
            if sys.platform.startswith('linux'):
                env['CXXFLAGS'] = env.get('CXXFLAGS', '') + ' -pthread'
                env['LDFLAGS'] = env.get('LDFLAGS', '') + ' -pthread'
            # Clang's implicit search paths can omit Conda's Boost library directory.
            prefix = env.get('CONDA_PREFIX')
            if prefix:
                env.setdefault('BOOST_INCLUDEDIR', str(pathlib.Path(prefix) / 'include'))
                env.setdefault('BOOST_LIBRARYDIR', str(pathlib.Path(prefix) / 'lib'))
            # This revision has a wrap redirect into libplugin; populate that
            # directory before Meson attempts to resolve the redirect.
            plugin = source / 'subprojects/libplugin'
            run(['git', 'clone', '--depth=1', '--branch', 'v0.3.4',
                 'https://github.com/4D-STAR/libplugin.git', plugin])
        report['dependencies'] = run([python, '-m', 'pip', 'freeze']).stdout
        if args.lock and not args.lock.exists():
            args.lock.parent.mkdir(parents=True, exist_ok=True)
            args.lock.write_text('\n'.join(line for line in report['dependencies'].splitlines()
                                         if not line.lower().startswith('meson-python')) + '\n')
        constraints = ['-c', str(args.lock.resolve())] if args.lock else []
        # Measure compiler paths independently, as in the small-package suite.
        control = output / 'toolchain-control'
        shutil.copytree(ROOT / 'tests/packages/rpath-no-dependencies', control)
        run([python, '-c', 'import mesonpy; mesonpy.Project(".", "build").build()'], cwd=control)
        control_binaries = inspect_binaries(control / 'build')
        report['toolchain_paths'] = next(info['paths'] for name, info in control_binaries.items()
                                         if pathlib.Path(name).name.startswith('_probe.'))
        shutil.rmtree(control)
        # Build a raw wheel, then hide its complete source/build checkout.
        build = source / 'build-rpath'
        command = [python, '-m', 'build', '--wheel', '--no-isolation', '--skip-dependency-check',
                   '-Cbuild-dir=' + str(build), f'-Ccompile-args=-j{args.jobs}']
        command.extend('-Csetup-args=' + option for option in config['setup'])
        run(command, cwd=source, timeout=args.build_timeout)
        report['source_diff'] = run(['git', 'diff', 'HEAD'], cwd=source).stdout
        report['install_plan'] = json.loads((build / 'meson-info/intro-install_plan.json').read_text())
        wheels = output / 'wheels'
        wheels.mkdir()
        wheel = next((source / 'dist').glob('*.whl'))
        raw_wheel = wheels / wheel.name
        shutil.copy2(wheel, raw_wheel)
        # Hide the entire checkout, including build products, before testing.
        source.rename(output / 'source-hidden')

        def audit(wheel, label):
            unpacked = output / (label + '-unpacked')
            with zipfile.ZipFile(wheel) as archive:
                archive.extractall(unpacked)
            binaries = inspect_binaries(unpacked)
            forbidden = [source, build_environment] if label == 'repaired' else [source]
            failures = check_paths(binaries, report['install_plan'], forbidden, report['toolchain_paths'])
            environment = output / (label + '-env')
            run([sys.executable, '-m', 'venv', environment])
            target_python = environment / 'bin/python'
            run([target_python, '-m', 'pip', 'install', *constraints, 'pytest', 'hypothesis', *config['runtime'], wheel])
            smoke_env_keys = ['PYTHONPATH', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH']
            for key in smoke_env_keys:
                env.pop(key, None)
            result = run([target_python, '-c', config['smoke']], check=False)
            if result.returncode:
                failures.append('Installed-wheel smoke test failed')
            report[label] = {'wheel': wheel.name, 'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                             'binaries': binaries, 'errors': failures}
            report['errors'].extend(f'{label}: {failure}' for failure in failures)

        audit(raw_wheel, 'raw')
        if args.repair:
            repaired = output / 'repaired'
            repaired.mkdir()
            if sys.platform == 'darwin':
                run([python, '-m', 'pip', 'install', 'delocate'])
                run([build_environment / 'bin/delocate-wheel', '-w', repaired, raw_wheel])
            else:
                run([python, '-m', 'pip', 'install', 'auditwheel'])
                run([build_environment / 'bin/auditwheel', 'repair', '-w', repaired, raw_wheel])
            build_environment.rename(output / 'build-env-hidden')
            audit(next(repaired.glob('*.whl')), 'repaired')
    except (Exception, KeyboardInterrupt) as error:
        report['errors'].append(str(error))
    finally:
        save_report()
    for error in report['errors']:
        print(error, file=sys.stderr)
    return bool(report['errors'])


if __name__ == '__main__':
    sys.exit(main())
