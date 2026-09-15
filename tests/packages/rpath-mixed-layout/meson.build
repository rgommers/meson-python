# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-mixed-layout', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
subdir('second')
subdir('first')
subdir('private')
py.extension_module('_probe', 'module.c', link_with: [first, second, private], install: true, subdir: 'probe', install_rpath: origin / 'private')
