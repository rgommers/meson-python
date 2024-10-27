# SPDX-FileCopyrightText: 2022 The meson-python developers
#
# SPDX-License-Identifier: MIT

example_lib = shared_library(
    'examplelib',
    'examplelib.c',
    install: true,
    install_dir: py.get_install_dir() / 'mypkg',
)

py.extension_module(
    '_example',
    '_examplemod.c',
    link_with: example_lib,
    install: true,
    subdir: 'mypkg',
    install_rpath: '$ORIGIN',
)

py.install_sources(
    ['__init__.py'],
    subdir: 'mypkg',
)
