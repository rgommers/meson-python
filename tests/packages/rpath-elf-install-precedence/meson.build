# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-elf-install-precedence', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
subdir('external')
subdir('private')
executable('probe-exe', 'main.c', link_with: private, install: true,
    install_dir: py.get_install_dir() / 'probe',
    link_args: '-Wl,-rpath,' + origin / 'external', install_rpath: origin / 'private')
