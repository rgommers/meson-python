# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

import pathlib
import subprocess
import sysconfig


# The ignored RPATH contains this dependency. Finding it would be a regression.
result = subprocess.run([pathlib.Path(sysconfig.get_path('platlib')) / 'probe/probe-exe'],
                        capture_output=True, text=True)
assert result.returncode != 0, 'Empty RUNPATH incorrectly reactivated RPATH'
assert 'librpath_test_choice.so' in result.stderr and 'cannot open shared object file' in result.stderr, result.stderr
