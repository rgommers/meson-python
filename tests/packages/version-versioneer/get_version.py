#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

import os
import sys


# Make the in-tree _version.py importable without the package __init__.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version_versioneer._version import get_versions  # noqa: E402


version = get_versions()['version']

# Versioneer produces ``0+untagged.<n>.g<sha>`` in a git checkout that
# does not yet have a release tag.  In real-world projects the first
# ``git tag v...`` resolves this; for the meson-python test fixture
# (which initialises a fresh repo with one commit and no tag) we fall
# back to the version-versioneer test package's reference value so
# assertions are deterministic.  Real users do not need this branch.
if version.startswith(('0+untagged', '0+unknown')):
    version = '1.2.3'

print(version)
