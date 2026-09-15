# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-ldflags', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
subdir('first')
py.extension_module('_probe', 'module.c', link_with: [first], install: true, subdir: 'probe')
