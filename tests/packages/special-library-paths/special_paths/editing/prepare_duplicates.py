# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

import pathlib
import sys


binary = pathlib.Path(sys.argv[1])
data = binary.read_bytes()

# Create two identical LC_RPATH commands to test removal of duplicate
# build-only paths. Linkers may reject or deduplicate identical paths,
# so the fixture links a distinct placeholder path instead. Replace its
# string after linking, preserving its length and the load-command layout.
old = b'@loader_path/remove this (seedx)\0'
new = b'@loader_path/remove this (build)\0'

# Wheel processing modifies this binary, so Ninja may run this script again
# when building another wheel. Only replace the placeholder if it is still
# present; otherwise leave the already-prepared or wheel-processed file alone.
if old in data:
    assert len(old) == len(new)
    assert data.count(old) == data.count(new) == 1, 'unexpected seed paths'
    binary.write_bytes(data.replace(old, new))
pathlib.Path(sys.argv[2]).write_text('prepared\n')
