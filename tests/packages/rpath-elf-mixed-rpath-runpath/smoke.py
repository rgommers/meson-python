# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

import pathlib
import subprocess
import sysconfig


subprocess.run([pathlib.Path(sysconfig.get_path('platlib')) / 'probe/probe-exe'], check=True)
