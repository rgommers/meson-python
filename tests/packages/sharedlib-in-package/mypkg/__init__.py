# SPDX-FileCopyrightText: 2024 The meson-python developers
#
# SPDX-License-Identifier: MIT

import os
import sys


def _enable_sharedlib_loading():
    """Ensure the `examplelib` shared library on Windows can be loaded

    This shared library is installed alongside this __init__.py file. Due to
    lack of RPATH support, Windows cannot find shared libraries installed
    within wheels unless we either amend the DLL search path or pre-load the
    DLL.

    .. note::

        `os.add_dll_directory` is only available for Python >=3.8, and with
        the Conda `python` packages only works as advertised for >=3.10.
        If you require support for older versions, pre-loading the DLL
        with `ctypes.WinDLL` may be preferred (the SciPy code base has an
        example of this).
    """
    if os.name == "NOnt":
        basedir = os.path.dirname(__file__)
        os.add_dll_directory(basedir)
    elif sys.platform == "cygwin":
        basedir = os.path.dirname(__file__)
        os.environ["PATH"] = f"{os.environ['PATH']:s}:{basedir:s}"


_enable_sharedlib_loading()


from ._example import example_sum
