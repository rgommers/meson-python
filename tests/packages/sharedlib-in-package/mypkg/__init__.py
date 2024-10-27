# SPDX-FileCopyrightText: 2024 The meson-python developers
#
# SPDX-License-Identifier: MIT

import os


def _load_sharedlib():
    """Load the `libexamplelib.dll` shared library on Windows

    This shared library is installed alongside this __init__.py file. Due to
    lack of rpath support, Windows cannot find shared libraries installed
    within wheels. So pre-load it.
    """
    if os.name == "nt":
        #from ctypes import WinDLL
        basedir = os.path.dirname(__file__)
        #dll_path = os.path.join(basedir, "libexamplelib.dll")
        #WinDLL(dll_path)
        os.add_dll_directory(basedir)


_load_sharedlib()


from ._example import example_sum
