# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project(
    'version-versioneer',
    version: run_command(
        ['get_version.py'],
        check: true,
    ).stdout().strip(),
)

py = import('python').find_installation()

py.install_sources(
    'version_versioneer/__init__.py',
    'version_versioneer/_version.py',
    subdir: 'version_versioneer',
)
