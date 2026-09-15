# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-in-package-flat', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
first = shared_library('first', 'first.c', install: true, install_dir: py.get_install_dir() / 'probe')
py.extension_module('_probe', 'module.c', link_with: [first], install: true, subdir: 'probe', install_rpath: origin)
