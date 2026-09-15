# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-macos-duplicates-remove', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
probe = py.extension_module('_probe', 'module.c', install: true, subdir: 'probe', link_args: '-Wl,-headerpad_max_install_names', build_rpath: '@loader_path/dupa:@loader_path/dupb')
custom_target('prepare-duplicates', input: probe, output: 'prepared.stamp',
    command: [py, files('prepare_binary.py'), '@INPUT@', '@OUTPUT@'], build_by_default: true)
