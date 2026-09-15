# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

paths = f'@origin@/private:@origin@/unused'
kwargs = meson.version().version_compare('<1.6') ? {
    'link_args': [f'-Wl,-rpath,@origin@/private', f'-Wl,-rpath,@origin@/unused'],
} : {'install_rpath': paths}

py.extension_module('_mixed', 'module.c', link_with: [first, second, private],
    install: true, subdir: 'rpath_mixed', kwargs: kwargs)
