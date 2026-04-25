# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project(
    'version-from-script',
    version: run_command(
        ['generate_version.py', '--print-version'],
        check: true,
    ).stdout().strip(),
)

py = import('python').find_installation()

version_gen = files('generate_version.py')

py.install_sources(
    'version_from_script/__init__.py',
    subdir: 'version_from_script',
)

custom_target(
    'write_version_file',
    output: '_version.py',
    command: [py, version_gen, '-o', '@OUTPUT@'],
    build_by_default: true,
    build_always_stale: true,
    install: true,
    install_dir: py.get_install_dir() / 'version_from_script',
)

meson.add_dist_script(py, version_gen, '-o', 'version_from_script/_version.py')
