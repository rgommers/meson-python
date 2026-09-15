# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-elf-both-tags-empty-runpath', 'c', version: '1.0.0')
py = import('python').find_installation(pure: false)
subdir('bad')
subdir('good')
probe = executable('probe-exe', 'main.c', link_with: choice, install: true,
    install_dir: py.get_install_dir() / 'probe',
    link_args: ['-Wl,--enable-new-dtags',
                '-Wl,-rpath,$ORIGIN/runpath-choice:$ORIGIN/good:$ORIGIN/rpath-choice'])
custom_target('prepare-both-tags', input: probe, output: 'prepared.stamp',
    command: [py, files('prepare_binary.py'), '@INPUT@', '@OUTPUT@', 'empty'],
    build_by_default: true)
