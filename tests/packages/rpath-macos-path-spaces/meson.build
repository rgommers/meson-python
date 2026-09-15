# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-macos-path-spaces', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
py.extension_module('_probe', 'module.c', install: true, subdir: 'probe',
    link_args: ['-Wl,-headerpad_max_install_names', '-Wl,-rpath,@loader_path/some path/(library)', '-Wl,-rpath,@loader_path/trailing '],
    build_rpath: '@loader_path/remove this (build)', install_rpath: '@loader_path/new path/(library)')
