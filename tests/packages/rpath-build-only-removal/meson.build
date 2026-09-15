# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-build-only-removal', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
py.extension_module('_probe', 'module.c', install: true, subdir: 'probe', install_rpath: '', build_rpath: origin / 'build-only')
