# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

py.install_sources('__init__.py', subdir: 'special_paths/layout')

sibling = shared_library(
    'sibling', 'sibling.c',
    install: true,
    install_dir: py.get_install_dir() / 'special_paths/layout',
)

subdir('sub')

py.extension_module(
    'example', 'module.c',
    link_with: [sibling, second],
    install: true,
    subdir: 'special_paths/layout',
    install_rpath: '@loader_path:@loader_path/sub',
)
