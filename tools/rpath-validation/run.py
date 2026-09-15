# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""One-time downstream builds. Every command and failure is retained in artifacts."""

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import venv
import zipfile

from collections import Counter

import tomllib


ROOT = pathlib.Path(__file__).resolve().parents[2]
# Reuse only the independent platform-tool reader, not backend RPATH code.
spec = importlib.util.spec_from_file_location('rpath_inspection', ROOT / 'tests/test_rpath_packages.py')
inspection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspection)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', choices=['numpy', 'gridfire', 'vapoursynth', 'dwave-optimization'])
    parser.add_argument('--backend', required=True, type=pathlib.Path)
    parser.add_argument('--output', required=True, type=pathlib.Path)
    parser.add_argument('--repair', action='store_true')
    parser.add_argument('--lock', type=pathlib.Path, help='Create once, then reuse build/runtime dependency constraints')
    args = parser.parse_args()
    config = json.loads((pathlib.Path(__file__).parent / 'projects.json').read_text())[args.project]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = output / 'source'
    backend = args.backend.resolve()
    report = {'project': args.project, 'configuration': config, 'commands': [], 'errors': []}
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)

    def run(command, cwd=output, check=True):
        result = subprocess.run([str(arg) for arg in command], cwd=cwd, env=env, capture_output=True, text=True)
        report['commands'].append({'command': list(map(str, command)), 'cwd': str(cwd),
                                   'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        (output / 'commands.json').write_text(json.dumps(report['commands'], indent=2) + '\n')
        print(f'[{result.returncode}] {" ".join(map(str, command))}', flush=True)
        if check and result.returncode:
            raise RuntimeError(result.stdout + '\n' + result.stderr)
        return result

    try:
        run(['git', 'init', source])
        run(['git', 'remote', 'add', 'origin', config['repository']], cwd=source)
        run(['git', 'fetch', '--depth=1', 'origin', config['revision']], cwd=source)
        run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=source)
        run(['git', 'submodule', 'update', '--init', '--recursive', '--depth=1'], cwd=source)
        report['submodules'] = run(['git', 'submodule', 'status', '--recursive'], cwd=source).stdout
        report['backend_commit'] = run(['git', 'rev-parse', 'HEAD'], cwd=backend).stdout.strip()
        report['compiler'] = run([*shlex.split(env.get('CC', 'cc')), '--version']).stdout
        build_environment = output / 'build-env'
        venv.EnvBuilder(with_pip=True).create(build_environment)
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
        build = source / 'build-rpath'
        command = [python, '-m', 'build', '--wheel', '--no-isolation', '--skip-dependency-check',
                   '-Cbuild-dir=' + str(build), '-Ccompile-args=-j2']
        command.extend('-Csetup-args=' + option for option in config['setup'])
        run(command, cwd=source)
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
            binaries = inspection.inspect(unpacked)
            failures = []
            for name, info in binaries.items():
                targets = [target for filename, target in report['install_plan'].get('targets', {}).items()
                           if pathlib.Path(filename).name == pathlib.Path(name).name]
                removed = {inspection.norm(path) for target in targets
                           for path in target.get('build_rpaths', [])}
                explicit = {inspection.norm(path) for target in targets
                            for path in (target.get('install_rpath') or '').split(':') if path}
                for path, count in Counter(info['paths']).items():
                    if not path or not path.strip('X'):
                        failures.append(f'{name}: empty or padding RPATH {path!r}')
                    if inspection.norm(path) in removed - explicit:
                        failures.append(f'{name}: retained build-only RPATH {path!r}')
                    if count > 1:
                        failures.append(f'{name}: duplicate {path!r} ({count} copies)')
                    if str(source) in path or (label == 'repaired' and str(build_environment) in path):
                        failures.append(f'{name}: build/source path {path!r}')
                    if sys.platform == 'darwin' and '$ORIGIN' in path:
                        failures.append(f'{name}: literal macOS $ORIGIN: {path!r}')
            environment = output / (label + '-env')
            venv.EnvBuilder(with_pip=True).create(environment)
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
    except Exception as error:
        report['errors'].append(str(error))
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return bool(report['errors'])


if __name__ == '__main__':
    sys.exit(main())
