# SPDX-FileCopyrightText: 2025 The meson-python developers
#
# SPDX-License-Identifier: MIT

import os
import shlex
import struct
import subprocess
import sys

from collections import Counter
from types import SimpleNamespace

import pytest
import wheel.wheelfile

import mesonpy

from mesonpy._rpath import _ELF, _MacOS, get_rpath, set_rpath


@pytest.mark.skipif(sys.platform in {'win32', 'cygwin'}, reason='requires RPATH support')
def test_rpath_get_set(wheel_sharedlib_in_package, tmp_path):
    artifact = wheel.wheelfile.WheelFile(wheel_sharedlib_in_package)
    artifact.extractall(tmp_path)
    obj = list(tmp_path.joinpath('mypkg').glob('_example.*'))[0]

    rpath = get_rpath(obj)
    assert len(rpath) == len(set(rpath))
    assert rpath

    set_rpath(obj, rpath, [])
    rpath = get_rpath(obj)
    assert rpath == []

    new_rpath = ['one', 'two']
    set_rpath(obj, rpath, new_rpath)
    rpath = get_rpath(obj)
    assert Counter(rpath) == Counter(new_rpath)

    new_rpath = ['one', 'three', 'two']
    set_rpath(obj, rpath, new_rpath)
    rpath = get_rpath(obj)
    assert Counter(rpath) == Counter(new_rpath)

    new_rpath = ['one']
    set_rpath(obj, rpath, new_rpath)
    rpath = get_rpath(obj)
    assert Counter(rpath) == Counter(new_rpath)


@pytest.mark.parametrize('value, expected', [
    (None, []), ('', []), ('one:two:one', ['one', 'two', 'one']), (':one::two:', ['one', 'two']),
])
def test_install_rpath_metadata(value, expected):
    files = mesonpy._map_to_wheel({'targets': {'module.so': {
        'destination': '{py_platlib}/module.so', 'install_rpath': value,
    }}}, [], [])
    assert files['platlib'][0].install_rpath == expected


@pytest.mark.parametrize('cls', [_ELF, _MacOS])
def test_rpath_merge(cls):
    origin = cls.origin
    old = [f'{origin}/build-a', '/external', f'{origin}/build-b', f'{origin}/user', 'XXXX', '/external']
    remove = [f'{origin}/build-a', f'{origin}/build-b']
    add = [f'{origin}/private', f'{origin}/user', f'{origin}/private']
    expected = [f'{origin}/private', f'{origin}/user', '/external', f'{origin}/../.pkg.mesonpy.libs']
    assert cls._rpath(old, add, remove, '../.pkg.mesonpy.libs') == expected
    assert cls._rpath(expected, add, remove, '../.pkg.mesonpy.libs') == expected
    assert cls._rpath(['/external'], [], [], '../.pkg.mesonpy.libs') == ['/external']
    assert cls._rpath([origin, '/external'], [origin], [origin], None) == [origin, '/external']
    assert cls._rpath([], [], [], None) == []


@pytest.mark.parametrize('anchor', ['$ORIGIN', '${ORIGIN}'])
def test_macos_literal_origin(anchor):
    assert _MacOS._rpath(['@loader_path/'], [anchor], ['@loader_path/'], None) == ['@loader_path']
    old = [anchor + '/build', anchor + '/user', '/external/$ORIGIN', '$ORIGIN_suffix']
    add = [anchor + '/private', '@loader_path/private']
    expected = ['@loader_path/private', '@loader_path/user', '/external/$ORIGIN',
                '$ORIGIN_suffix', '@loader_path/../libs']
    assert _MacOS._rpath(old, add, ['@loader_path/build'], '../libs') == expected
    assert _MacOS._rpath(expected, add, [anchor + '/build'], '../libs') == expected


def test_macos_parse_paths(mocker):
    run = mocker.patch('mesonpy._rpath.subprocess.run')
    run.return_value.stdout = '''binary (architecture arm64):
Load command 1
          cmd LC_RPATH
      cmdsize 64
         path /some path/(library)/lib (offset 12)
Load command 2
          cmd LC_RPATH
         path @loader_path/private (offset 12)
Load command 3
          cmd LC_RPATH
         path /path with trailing space  (offset 12)
binary (architecture x86_64):
Load command 1
          cmd LC_RPATH
         path @loader_path/private (offset 12)
'''
    assert _MacOS._get_rpaths('binary', all_archs=True) == {
        'arm64': ['/some path/(library)/lib', '@loader_path/private', '/path with trailing space '],
        'x86_64': ['@loader_path/private'],
    }


@pytest.mark.parametrize('old, new, deletions', [
    (['one', 'one'], ['one'], ['one']),
    (['one', 'one'], [], ['one', 'one']),
    (['one', 'one', 'two'], ['one', 'three'], ['one', 'two']),
    (['one'], ['one'], []),
])
def test_macos_duplicate_commands(mocker, old, new, deletions):
    run = mocker.patch('mesonpy._rpath.subprocess.run')
    _MacOS._set_rpath('binary', old, new)
    deleted = []
    for call in run.call_args_list:
        args = call.args[0]
        assert len(args) > 2, 'install_name_tool must not be called without operations'
        paths = [args[i + 1] for i, arg in enumerate(args) if arg == '-delete_rpath']
        assert len(paths) == len(set(paths))
        deleted += paths
    assert Counter(deleted) == Counter(deletions)


def test_macos_universal_noop(mocker):
    run = mocker.patch('mesonpy._rpath.subprocess.run')
    old = {'arm64': ['/external/arm64', '/install'], 'x86_64': ['/external/x86_64', '/install']}
    new = {arch: list(reversed(paths)) for arch, paths in old.items()}
    _MacOS._update_rpaths('binary', old, new)
    run.assert_not_called()


@pytest.mark.parametrize('bits', [1, 2], ids=['elf32', 'elf64'])
@pytest.mark.parametrize('endian', ['<', '>'], ids=['little', 'big'])
@pytest.mark.parametrize('tags, expected', [([], False), ([15], True), ([29], False), ([15, 29], False)])
def test_elf_rpath_tag(tmp_path, bits, endian, tags, expected):
    header = struct.Struct(endian + ('HHIIIIIHHHHHH' if bits == 1 else 'HHIQQQIHHHHHH'))
    program = struct.Struct(endian + ('IIIIIIII' if bits == 1 else 'IIQQQQQQ'))
    dynamic = struct.Struct(endian + ('iI' if bits == 1 else 'qQ'))
    phoff = 16 + header.size
    offset = phoff + program.size
    entries = b''.join(dynamic.pack(tag, 0) for tag in [*tags, 0])
    ph = ((2, offset, 0, 0, len(entries), len(entries), 0, 0) if bits == 1 else
          (2, 0, offset, 0, 0, len(entries), len(entries), 0))
    obj = tmp_path / 'binary'
    obj.write_bytes(
        b'\x7fELF' + bytes([bits, 1 if endian == '<' else 2, 1]) + b'\0' * 9
        + header.pack(3, 0, 1, 0, phoff, 0, 0, phoff, program.size, 1, 0, 0, 0)
        + program.pack(*ph) + entries)
    assert _ELF._has_rpath(obj) == expected


def compile_c(output, code, *args):
    compiler = shlex.split(os.environ.get('CC', 'cc'))
    subprocess.run([*compiler, '-x', 'c', '-', *args, '-o', os.fspath(output)], input=code, text=True, check=True)


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='requires ELF and GNU linker flags')
@pytest.mark.parametrize('dtags', ['--disable-new-dtags', '--enable-new-dtags'])
def test_elf_rewrite_idempotent(tmp_path, dtags):
    obj = tmp_path / 'libprobe.so'
    compile_c(obj, 'int probe(void) { return 42; }', '-shared', '-fPIC', f'-Wl,{dtags},-rpath,$ORIGIN/build')
    original_type = _ELF._has_rpath(obj)
    assert original_type == (dtags == '--disable-new-dtags')
    for _ in range(2):
        _ELF.fix_rpath(obj, ['$ORIGIN/a', '$ORIGIN/b'], ['$ORIGIN/build'], None)
        paths = _ELF.get_rpath(obj)
        assert paths[:2] == ['$ORIGIN/a', '$ORIGIN/b']
        assert len(paths) == len(set(paths))
        assert '$ORIGIN/build' not in paths
        assert _ELF._has_rpath(obj) == original_type


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='requires ELF and GNU linker flags')
def test_elf_transitive_dependency(tmp_path, monkeypatch):
    monkeypatch.delenv('LD_LIBRARY_PATH', raising=False)
    libdir = tmp_path / 'lib'
    libdir.mkdir()
    leaf, middle, exe = libdir / 'libleaf.so', libdir / 'libmiddle.so', tmp_path / 'probe'
    compile_c(leaf, 'int leaf(void) { return 42; }', '-shared', '-fPIC', '-Wl,-soname,libleaf.so')
    compile_c(middle, 'extern int leaf(void); int middle(void) { return leaf(); }',
              '-shared', '-fPIC', f'-L{libdir}', '-lleaf', '-Wl,-soname,libmiddle.so')
    subprocess.run(['patchelf', '--remove-rpath', middle], check=True)
    compile_c(exe, 'extern int middle(void); int main(void) { return middle() != 42; }',
              f'-L{libdir}', '-lmiddle', f'-Wl,-rpath-link,{libdir}', '-Wl,--disable-new-dtags,-rpath,$ORIGIN/lib')
    subprocess.run([exe], check=True)
    # Exercise the newly reached wheel-builder path: no relocated libraries.
    builder = SimpleNamespace(_has_internal_libs=False)
    writer = SimpleNamespace(write=lambda *args: None)
    mesonpy._WheelBuilder._install_path(builder, writer, exe, tmp_path / 'installed', ['$ORIGIN/extra'], [])
    subprocess.run([exe], check=True)


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='requires ELF and GNU linker flags')
def test_elf_install_search_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv('LD_LIBRARY_PATH', raising=False)
    for dirname, number in [('external', 7), ('private', 42)]:
        directory = tmp_path / dirname
        directory.mkdir()
        compile_c(directory / 'libchoice.so', f'int choice(void) {{ return {number}; }}',
                  '-shared', '-fPIC', '-Wl,-soname,libchoice.so')
    exe = tmp_path / 'probe'
    compile_c(exe, 'extern int choice(void); int main(void) { return choice() != 42; }',
              f'-L{tmp_path / "private"}', '-lchoice', '-Wl,-rpath,$ORIGIN/external')
    assert subprocess.run([exe]).returncode == 1
    _ELF.fix_rpath(exe, ['$ORIGIN/private'], [], None)
    subprocess.run([exe], check=True)


@pytest.mark.skipif(sys.platform != 'darwin', reason='requires Apple tools')
@pytest.mark.parametrize('keep', [True, False])
def test_macos_existing_duplicates(tmp_path, keep):
    obj = tmp_path / 'libprobe.dylib'
    compile_c(obj, 'int probe(void) { return 42; }', '-dynamiclib',
              '-Wl,-headerpad_max_install_names,-rpath,@loader_path/a,-rpath,@loader_path/b')
    # The linker may deduplicate identical inputs, and install_name_tool
    # refuses to add a duplicate. Replace an equal-length load-command path.
    data = obj.read_bytes()
    assert data.count(b'@loader_path/b\0') == 1
    obj.write_bytes(data.replace(b'@loader_path/b\0', b'@loader_path/a\0'))
    old = _MacOS.get_rpath(obj)
    assert old.count('@loader_path/a') == 2
    remove = [] if keep else ['@loader_path/a']
    _MacOS.fix_rpath(obj, ['/new path/(library)'], remove, None)
    expected = [path for path in old if path != '@loader_path/a'] + ['/new path/(library)']
    if keep:
        expected.append('@loader_path/a')
    assert Counter(_MacOS.get_rpath(obj)) == Counter(expected)
    before = obj.read_bytes()
    _MacOS.fix_rpath(obj, ['/new path/(library)'], remove, None)
    assert obj.read_bytes() == before
    subprocess.run([sys.executable, '-c', 'import ctypes, sys; assert ctypes.CDLL(sys.argv[1]).probe() == 42', obj],
                   check=True)


@pytest.mark.skipif(sys.platform != 'darwin', reason='requires Apple tools')
def test_macos_universal_rpaths(tmp_path):
    slices = []
    for arch in ['arm64', 'x86_64']:
        thin = tmp_path / arch
        compile_c(thin, 'int probe(void) { return 42; }', '-dynamiclib', '-arch', arch,
                  f'-Wl,-headerpad_max_install_names,-rpath,/build/{arch},-rpath,/external/{arch},-rpath,/common')
        slices.append(thin)
    obj = tmp_path / 'universal.dylib'
    subprocess.run(['lipo', '-create', *slices, '-output', obj], check=True)
    old = _MacOS._get_rpaths(obj, all_archs=True)
    _MacOS.fix_rpath(obj, ['/install'], ['/build/arm64', '/build/x86_64'], None)
    paths = _MacOS._get_rpaths(obj, all_archs=True)
    assert set(paths) == {'arm64', 'x86_64'}
    for arch, entries in paths.items():
        expected = ['/install'] + [path for path in old[arch] if path != f'/build/{arch}']
        assert Counter(entries) == Counter(expected)
        assert entries.count('/common') == 1
    before = obj.read_bytes()
    _MacOS.fix_rpath(obj, ['/install'], ['/build/arm64', '/build/x86_64'], None)
    assert obj.read_bytes() == before
    subprocess.run([sys.executable, '-c', 'import ctypes, sys; assert ctypes.CDLL(sys.argv[1]).probe() == 42', obj],
                   check=True)
