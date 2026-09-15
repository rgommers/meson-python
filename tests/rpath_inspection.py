# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Independent RPATH inspection shared by the package tests and downstream runner.

This module needs only the standard library and platform inspection tools.
Paths are kept as lists so duplicate entries remain visible.
"""

import posixpath
import re
import subprocess
import sys


PLATFORM = 'linux' if sys.platform.startswith('linux') else sys.platform


def is_native(path):
    if not path.is_file():
        return False
    with path.open('rb') as stream:
        header = stream.read(20)
    if header[:4] == b'\x7fELF':
        endian = 'little' if header[5] == 1 else 'big'
        return int.from_bytes(header[16:18], endian) in {2, 3}
    if header[:4] in {b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe'}:
        return int.from_bytes(header[12:16], 'little') in {2, 6, 8}
    if header[:4] in {b'\xfe\xed\xfa\xcf', b'\xfe\xed\xfa\xce'}:
        return int.from_bytes(header[12:16], 'big') in {2, 6, 8}
    return False


def read_rpaths(path):
    """Use platform tools, never the RPATH implementation under test."""
    if PLATFORM == 'linux':
        result = subprocess.run(['readelf', '-dW', path], capture_output=True, text=True, check=True)
        tags = re.findall(r'\((RPATH|RUNPATH)\).*?\[(.*)\]', result.stdout)
        return {'tags': [tag for tag, _ in tags],
                'paths_by_tag': {tag: value.split(':') if value else [] for tag, value in tags},
                'paths': [entry for _, value in tags for entry in value.split(':')], 'raw': result.stdout}
    result = subprocess.run(['otool', '-l', path], capture_output=True, text=True, check=True)
    paths = []
    pending = False
    for line in result.stdout.splitlines():
        line = line.lstrip()
        if line.startswith('cmd '):
            pending = line.split() == ['cmd', 'LC_RPATH']
        elif pending and line.startswith('path '):
            match = re.fullmatch(r'path (.*) \(offset [0-9]+\)', line)
            assert match, f'Unrecognized otool path: {line!r}'
            paths.append(match[1])
            pending = False
    return {'tags': ['LC_RPATH'] * len(paths), 'paths': paths, 'raw': result.stdout}


def inspect_binaries(directory):
    return {path.relative_to(directory).as_posix(): read_rpaths(path)
            for path in sorted(directory.rglob('*')) if is_native(path)}


def normalize_rpath(path):
    # Accept Meson's equivalent origin/ and origin spellings, while preserving
    # meaningful spaces. Duplicate detection always examines raw entries first.
    for anchor in ['$ORIGIN', '@loader_path']:
        if path == anchor or path.startswith(anchor + '/'):
            suffix = posixpath.normpath(path[len(anchor):].lstrip('/'))
            return anchor if suffix == '.' else anchor + '/' + suffix
    return posixpath.normpath(path)
