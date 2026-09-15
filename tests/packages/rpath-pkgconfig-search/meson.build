# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-pkgconfig-search', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
external = dependency('external', method: 'pkg-config')
py.extension_module('_probe', 'module.c', dependencies: external, install: true, subdir: 'probe')
