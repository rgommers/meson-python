# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

from version_versioneer._version import get_versions


__version__ = get_versions()['version']

__all__ = ['__version__']
