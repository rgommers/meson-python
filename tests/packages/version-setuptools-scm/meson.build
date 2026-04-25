# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project(
    'version-setuptools-scm',
    version: run_command(
        ['get_version.py'],
        check: true,
    ).stdout().strip(),
)
