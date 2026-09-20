# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

py.install_sources('__init__.py', subdir: 'special_paths/editing')

# Include spaces, parentheses, and a trailing space in the runtime paths.
# Link two distinct paths, then use prepare_duplicates.py to make them
# identical: linkers may reject or deduplicate repeated RPATH arguments.
example = py.extension_module(
    'example', 'module.c',
    install: true,
    subdir: 'special_paths/editing',
    link_args: [
        '-Wl,-headerpad_max_install_names',
        '-Wl,-rpath,@loader_path/some path/(library)',
        '-Wl,-rpath,@loader_path/trailing ',
        '-Wl,-rpath,@loader_path/remove this (seedx)',
    ],
    build_rpath: '@loader_path/remove this (build)',
    install_rpath: '@loader_path/new path/(library)',
)
custom_target(
    'prepare-duplicates',
    input: example,
    output: 'prepared.stamp',
    command: [py, files('prepare_duplicates.py'), '@INPUT@', '@OUTPUT@'],
    build_by_default: true,
)
