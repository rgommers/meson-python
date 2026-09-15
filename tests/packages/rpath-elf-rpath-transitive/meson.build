# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-elf-rpath-transitive', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' ? '@loader_path' : '$ORIGIN'
add_project_link_arguments('-Wl,--disable-new-dtags', language: 'c')
subdir('leaf')
subdir('middle')
executable('probe-exe', 'main.c', link_with: middle, install: true,
    install_dir: py.get_install_dir() / 'probe', install_rpath: origin / 'lib')
