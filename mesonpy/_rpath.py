# SPDX-FileCopyrightText: 2023 The meson-python developers
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import typing

from collections import Counter


if typing.TYPE_CHECKING:
    from typing import Dict, List, Optional, TypeVar, Union
    Path = Union[str, os.PathLike[str]]
    T = TypeVar('T')


def unique(values: List[T]) -> List[T]:
    r = []
    for value in values:
        if value not in r:
            r.append(value)
    return r


class RPATH:

    origin = '$ORIGIN'

    @staticmethod
    def get_rpath(filepath: Path) -> List[str]:
        raise NotImplementedError

    @staticmethod
    def set_rpath(filepath: Path, old: List[str], rpath: List[str]) -> None:
        raise NotImplementedError

    @classmethod
    def fix_rpath(cls, filepath: Path, add: List[str], remove: List[str], libs_relative_path: Optional[str]) -> None:
        old_rpath = cls.get_rpath(filepath)
        new_rpath = cls._rpath(old_rpath, add, remove, libs_relative_path)
        if new_rpath != old_rpath:
            cls.set_rpath(filepath, old_rpath, new_rpath)

    @classmethod
    def _rpath(cls, old_rpath: List[str], add: List[str], remove: List[str],
               libs_relative_path: Optional[str]) -> List[str]:

        # Meson adds a padding entry to RPATH composed of enough `X`
        # characters to reserve enough space in the ELF header to hold
        # the final installation RPATH. Remove this entry and other
        # entries to be removed.
        # Match Meson's install-time precedence: explicit paths come first.
        new_rpath = add + [path for path in old_rpath if path.strip('X') and path not in remove]

        # When an executable, library, or Python extension module is
        # dynamically linked to a library built as part of the project, Meson
        # adds a build RPATH pointing to the build directory, in the form of a
        # relative RPATH entry. We can use the presence of any RPATH entries
        # relative to ``$ORIGIN`` as an indicator that the installed object
        # depends on shared libraries internal to the project. In this case we
        # need to add an RPATH entry pointing to the meson-python shared
        # library install location. This heuristic is not perfect: RPATH
        # entries relative to ``$ORIGIN`` can exist for other reasons.
        # However, this only results in harmless additional RPATH entries.
        if libs_relative_path and any(path.startswith(cls.origin) for path in old_rpath):
            new_rpath.append(os.path.join(cls.origin, libs_relative_path))

        return unique(new_rpath)


class _Windows(RPATH):

    @classmethod
    def fix_rpath(cls, filepath: Path, add: List[str], remove: List[str], libs_relative_path: Optional[str]) -> None:
        pass


class _MacOS(RPATH):

    origin = '@loader_path'

    @classmethod
    def _rpath(cls, old_rpath: List[str], add: List[str], remove: List[str],
               libs_relative_path: Optional[str]) -> List[str]:
        # Historical projects use $ORIGIN in install_rpath on every platform.
        # Meson translates its generated build paths on macOS, but installation
        # metadata can still contain the ELF spelling. Compare and emit paths
        # using the native anchor, including any subdirectory suffix.
        def native(path: str) -> str:
            anchor, separator, suffix = path.partition('/')
            if anchor in ('$ORIGIN', '${ORIGIN}'):
                return cls.origin + separator + suffix
            return path

        return super()._rpath(
            [native(path) for path in old_rpath], [native(path) for path in add],
            [native(path) for path in remove], libs_relative_path)

    @staticmethod
    def _get_rpaths(filepath: Path, all_archs: bool = False) -> Dict[str, List[str]]:
        args = ['-arch', 'all'] if all_archs else []
        r = subprocess.run(['otool', *args, '-l', os.fspath(filepath)], capture_output=True, check=True, text=True)
        rpaths: Dict[str, List[str]] = {}
        arch = ''
        rpath_tag = False
        for line in r.stdout.splitlines():
            match = re.match(r'^.* \(architecture (.+)\):$', line)
            if match:
                arch = match[1]
                rpaths.setdefault(arch, [])
                rpath_tag = False
            line = line.strip()
            if line.startswith('cmd '):
                rpath_tag = line.split() == ['cmd', 'LC_RPATH']
            elif rpath_tag and line.startswith('path '):
                # Paths may contain whitespace and parentheses. Only the
                # trailing offset annotation belongs to otool's output.
                path = re.sub(r' \(offset \d+\)$', '', line[5:])
                rpaths.setdefault(arch, []).append(path)
                rpath_tag = False
        return rpaths or {'': []}

    @classmethod
    def get_rpath(cls, filepath: Path) -> List[str]:
        return [path for paths in cls._get_rpaths(filepath).values() for path in paths]

    @classmethod
    def fix_rpath(cls, filepath: Path, add: List[str], remove: List[str], libs_relative_path: Optional[str]) -> None:
        old = cls._get_rpaths(filepath, all_archs=True)
        new = {arch: cls._rpath(paths, add, remove, libs_relative_path) for arch, paths in old.items()}
        cls._update_rpaths(filepath, old, new)

    @classmethod
    def set_rpath(cls, filepath: Path, old: List[str], rpath: List[str]) -> None:
        # Inspect each slice: the host architecture's paths may differ from
        # those in other slices of a universal binary.
        paths = cls._get_rpaths(filepath, all_archs=True)
        cls._update_rpaths(filepath, paths, {arch: unique(rpath) for arch in paths})

    @classmethod
    def _update_rpaths(cls, filepath: Path, old: Dict[str, List[str]], new: Dict[str, List[str]]) -> None:
        # Like Meson, the macOS writer preserves the order of retained paths.
        # An order-only difference must not cause another edit or lipo pass.
        if all(Counter(paths) == Counter(new[arch]) for arch, paths in old.items()):
            return
        if len(unique(list(old.values()))) == 1 and len(unique(list(new.values()))) == 1:
            cls._set_rpath(filepath, next(iter(old.values())), next(iter(new.values())))
            return

        # install_name_tool applies every operation to every architecture.
        # Edit slices separately when they have different paths or counts.
        with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(filepath))) as tmp:
            slices = []
            for arch, paths in old.items():
                thin = os.path.join(tmp, arch)
                subprocess.run(['lipo', os.fspath(filepath), '-thin', arch, '-output', thin], check=True)
                cls._set_rpath(thin, paths, new[arch])
                slices.append(thin)
            output = os.path.join(tmp, 'universal')
            subprocess.run(['lipo', '-create', *slices, '-output', output], check=True)
            shutil.copystat(filepath, output)
            os.replace(output, filepath)

    @staticmethod
    def _set_rpath(filepath: Path, old: List[str], rpath: List[str]) -> None:
        # This implementation does not preserve the ordering of RPATH
        # entries. Meson does the same, thus it should not be a problem.
        add = [path for path in rpath if path not in old]
        remove = {path: old.count(path) - (path in rpath) for path in unique(old)}
        # Apple's tool removes one occurrence per invocation and rejects
        # repeated -delete_rpath options for the same path in one invocation.
        while add or any(remove.values()):
            args: List[str] = []
            for path in add:
                args += ['-add_rpath', path]
            add = []
            for path, count in remove.items():
                if count:
                    args += ['-delete_rpath', path]
                    remove[path] -= 1
            subprocess.run(['install_name_tool', *args, os.fspath(filepath)], check=True)


class _SunOS5(RPATH):

    @staticmethod
    def get_rpath(filepath: Path) -> List[str]:
        rpath = []
        r = subprocess.run(['/usr/bin/elfedit', '-r', '-e', 'dyn:rpath', os.fspath(filepath)],
            capture_output=True, check=True, text=True)
        for line in [x.split() for x in r.stdout.split('\n')]:
            if len(line) >= 4 and line[1] in ['RPATH', 'RUNPATH']:
                for path in line[3].split(':'):
                    if path not in rpath:
                        rpath.append(path)
        return rpath

    @staticmethod
    def set_rpath(filepath: Path, old: List[str], rpath: List[str]) -> None:
        subprocess.run(['/usr/bin/elfedit', '-e', 'dyn:rpath ' + ':'.join(rpath), os.fspath(filepath)], check=True)


class _ELF(RPATH):

    @staticmethod
    def get_rpath(filepath: Path) -> List[str]:
        r = subprocess.run(['patchelf', '--print-rpath', os.fspath(filepath)], capture_output=True, check=True, text=True)
        return [x for x in r.stdout.strip().split(':') if x]

    @staticmethod
    def set_rpath(filepath: Path, old: List[str], rpath: List[str]) -> None:
        if not rpath:
            subprocess.run(['patchelf', '--remove-rpath', os.fspath(filepath)], check=True)
            return
        args = ['--force-rpath'] if _ELF._has_rpath(filepath) else []
        subprocess.run(['patchelf', *args, '--set-rpath', ':'.join(rpath), os.fspath(filepath)], check=True)

    @staticmethod
    def _has_rpath(filepath: Path) -> bool:
        # patchelf converts DT_RPATH to DT_RUNPATH by default, changing both
        # search precedence and transitive dependency resolution. Read the
        # dynamic tags directly to avoid requiring readelf at build time.
        with open(filepath, 'rb') as f:
            ident = f.read(16)
            if ident[:4] != b'\x7fELF' or ident[4] not in (1, 2) or ident[5] not in (1, 2):
                raise ValueError(f'Invalid ELF header: {os.fspath(filepath)}')
            endian = '<' if ident[5] == 1 else '>'
            bits = ident[4]
            header = struct.Struct(endian + ('HHIIIIIHHHHHH' if bits == 1 else 'HHIQQQIHHHHHH'))
            values = header.unpack(f.read(header.size))
            phoff, phentsize, phnum = values[4], values[8], values[9]
            program = struct.Struct(endian + ('IIIIIIII' if bits == 1 else 'IIQQQQQQ'))
            dynamic = struct.Struct(endian + ('iI' if bits == 1 else 'qQ'))
            has_rpath = False
            for index in range(phnum):
                f.seek(phoff + index * phentsize)
                ph = program.unpack(f.read(program.size))
                if ph[0] != 2:  # PT_DYNAMIC
                    continue
                offset, size = (ph[1], ph[4]) if bits == 1 else (ph[2], ph[5])
                f.seek(offset)
                for _ in range(size // dynamic.size):
                    tag, _ = dynamic.unpack(f.read(dynamic.size))
                    if tag == 0:  # DT_NULL
                        break
                    if tag == 29:  # DT_RUNPATH takes precedence over DT_RPATH
                        return False
                    if tag == 15:  # DT_RPATH
                        has_rpath = True
            return has_rpath


if sys.platform == 'win32' or sys.platform == 'cygwin':
    _cls = _Windows
elif sys.platform == 'darwin':
    _cls = _MacOS
elif sys.platform == 'sunos5':
    _cls = _SunOS5
else:
    _cls = _ELF

get_rpath = _cls.get_rpath
set_rpath = _cls.set_rpath
fix_rpath = _cls.fix_rpath
