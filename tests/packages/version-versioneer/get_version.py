#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

import os
import sys


# Make the in-tree _version.py importable without the package __init__.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version_versioneer._version import get_versions  # noqa: E402


print(get_versions()['version'])
