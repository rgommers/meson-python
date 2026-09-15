# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-elf-mixed-rpath-runpath', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
origin = '$ORIGIN'
subdir('leaf')
subdir('middle')
executable('probe-exe', 'main.c', link_with: middle, install: true,
    install_dir: py.get_install_dir() / 'probe', install_rpath: origin / 'middle',
    link_args: '-Wl,--disable-new-dtags')
