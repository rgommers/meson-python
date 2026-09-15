# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Prepare both ELF tags without using the backend's RPATH implementation.

The CI targets are ELF64 little-endian. Reuse DT_DEBUG (irrelevant to this
probe's execution) for DT_RPATH and split the reserved RUNPATH string in place.
No sections move and no dependency or executable code changes.
"""

import pathlib
import struct
import sys


binary = pathlib.Path(sys.argv[1])
data = bytearray(binary.read_bytes())
assert data[:6] == b'\x7fELF\x02\x01', 'fixture requires little-endian ELF64'
section_offset = struct.unpack_from('<Q', data, 40)[0]
section_size, section_count = struct.unpack_from('<HH', data, 58)
sections = [struct.unpack_from('<IIQQQQIIQQ', data, section_offset + i * section_size)
            for i in range(section_count)]
dynamic = next(section for section in sections if section[1] == 6)  # SHT_DYNAMIC
strings = sections[dynamic[6]]  # sh_link identifies the dynamic string table
seed = b'$ORIGIN/runpath-choice:$ORIGIN/good:$ORIGIN/rpath-choice'
start = data.find(seed, strings[4], strings[4] + strings[5])
# Ninja may rerun this target after wheel processing edited its input. Only
# prepare freshly linked seed strings; never restore the original tag pair.
if start != -1:
    entries = {tag: offset for offset in range(dynamic[4], dynamic[4] + dynamic[5], 16)
               for tag, _ in [struct.unpack_from('<qQ', data, offset)] if tag}
    assert 21 in entries and 29 in entries and 15 not in entries, 'unexpected seed tags'
    separator = start + seed.rindex(b':')
    data[separator] = 0
    data[start + len(seed)] = 0  # Exclude any compiler-added suffix.
    rpath = separator + 1 - strings[4]
    runpath = (separator if sys.argv[3] == 'empty' else start) - strings[4]
    struct.pack_into('<qQ', data, entries[21], 15, rpath)  # DT_DEBUG -> DT_RPATH
    struct.pack_into('<qQ', data, entries[29], 29, runpath)  # DT_RUNPATH
    binary.write_bytes(data)
pathlib.Path(sys.argv[2]).write_text('prepared\n')
