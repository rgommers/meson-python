# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

import pathlib
import sys


binary = pathlib.Path(sys.argv[1])
data = binary.read_bytes()
a = b'@loader_path/dupa\0'
b = b'@loader_path/dupb\0'
# After wheel processing, Ninja may revisit this target because its input
# was edited. Only patch freshly linked seed commands; do not recreate bugs.
if b in data:
    assert data.count(a) == data.count(b) == 1, 'unexpected seed LC_RPATH entries'
    binary.write_bytes(data.replace(b, a))
pathlib.Path(sys.argv[2]).write_text('prepared\n')
