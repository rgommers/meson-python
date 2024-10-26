.. SPDX-FileCopyrightText: 2024 The meson-python developers
..
.. SPDX-License-Identifier: MIT

.. _shared-libraries:

**********************
Using shared libraries
**********************

Python projects may build shared libraries as part of their project, or link
with shared libraries from a dependency. This tends to be a common source of
issues, hence this page aims to explain how to include shared libraries in
wheels, any limitations and gotchas, and how support is implemented in
``meson-python`` under the hood.

We distinguish between *internal* shared libraries, i.e. they're built as part
of the build executed by ``meson-python``, and *external* shared libraries that
are only linked against from targets (usually Python extension modules) built
by ``meson-python``. For internal shared libraries, we also distinguish whether
the shared library is being installed to its default location (i.e. ``libdir``,
usually something like ``<prefix>/lib/``) or to a location in ``site-packages``
within the Python package install tree. All these scenarios are (or will be)
supported, with some caveats:

+-----------------------+------------------+---------+-------+-------+
| shared library source | install location | Windows | macOS | Linux |
+=======================+==================+=========+=======+=======+
| internal              | libdir           | no (1)  | ✓     | ✓     |
+-----------------------+------------------+---------+-------+-------+
| internal              | site-packages    | ✓       | ✓     | ✓     |
+-----------------------+------------------+---------+-------+-------+
| external              | n/a              | ✓ (2)   | ✓     | ✓     |
+-----------------------+------------------+---------+-------+-------+

.. TODO: add subproject as a source

1: Internal shared libraries on Windows cannot be automaticall handled
correctly, and currently ``meson-python`` therefore raises an error for them.
`PR meson-python#551 <https://github.com/mesonbuild/meson-python/pull/551>`__
may improve that situation in the near future.

2: External shared libraries require ``delvewheel`` usage on Windows (or
some equivalent way, like amending the DLL search path to include the directory
in which the external shared library is located). Due to the lack of RPATH
support on Windows, there is no good way around this.


Internal shared libraries
=========================

A shared library produced by ``library()`` or ``shared_library()`` built like this

.. code-block:: meson

    example_lib = shared_library(
        'example',
        'examplelib.c',
        install: true,
    )

is installed to ``libdir`` by default. If the only reason the shared library exists
is to be used inside the Python package being built, then it is best to modify
the install location to be within the Python package itself:

.. code-block:: python

   install_path: py.get_install_dir() / 'mypkg/subdir'

Then an extension module in the same install directory can link against the
shared library in a portable manner by using ``install_rpath``:

.. code-block:: meson

    py3.extension_module('_extmodule',
        '_extmodule.c',
        link_with: example_lib,
        install: true,
        subdir: 'mypkg/subdir',
        install_rpath: '$ORIGIN'
    )

The above method will work as advertised on macOS and Linux; ``meson-python`` does
nothing special for this case. On Windows, due to the lack of RPATH support, we
need to preload the shared library on import to make this work by adding this
to ``mypkg/subdir/__init__.py``:

.. code-block:: python

    def _load_sharedlib():
        """Load the `example_lib.dll` shared library on Windows

        This shared library is installed alongside this __init__.py file. Due to
        lack of rpath support, Windows cannot find shared libraries installed
        within wheels. So pre-load it.
        """
        if os.name == "nt":
            import ctypes
            try:
                from ctypes import WinDLL
                basedir = os.path.dirname(__file__)
            except:
                pass
            else:
                dll_path = os.path.join(basedir, "example_lib.dll")
                if os.path.exists(dll_path):
                    WinDLL(dll_path)

    _load_sharedlib()

If an internal shared library is not only used as part of a Python package, but
for example also as a regular shared library in a C/C++ project or as a
standalone library, then the method shown above won't work - the library has to
be installed to the default ``libdir`` location. In that case, ``meson-python``
will detect that the library is going to be installed to ``libdir`` - which is
not a recommended install location for wheels, and not supported by
``meson-python``. Instead, ``meson-python`` will do the following *on platforms
other than Windows*:

1. Install the shared library to ``<project-name>.mesonpy.libs`` (i.e., a
   top-level directory in the wheel, which on install will end up in
   ``site-packages``).
2. Rewrite RPATH entries for install targets that depend on the shared library
   to point to that new install location instead.

This will make the shared library work automatically, with no other action needed
from the package author. *However*, currently an error is raised for this situation
on Windows. This is documented also in :ref:`reference-limitations`.


External shared libraries
=========================

External shared libraries are installed somewhere on the build machine, and
usually detected by a ``dependency()`` or ``compiler.find_library()`` call in a
``meson.build`` file. When a Python extension module or executable uses the
dependency, the shared library will be linked against at build time. On
platforms other than Windows, an RPATH entry is then added to the built
extension modulo or executable, which allows the shared library to be loaded at
runtime.

.. note::

   An RPATH entry alone is not always enough - if the directory that the shared
   library is located in is not on the loader search path, then it may go
   missing at runtime. See, e.g., `meson#2121 <https://github.com/mesonbuild/meson/issues/2121>`__
   and `meson#13046 <https://github.com/mesonbuild/meson/issues/13046>`__ for
   issues this can cause.

   TODO: describe workarounds, e.g. via ``-Wl,-rpath`` or setting ``LD_LIBRARY_PATH``.

On Windows, the shared library can either be preloaded, or vendored with
``delvewheel`` in order to make the built Python package usable locally.


Publishing wheels which depend on external shared libraries
-----------------------------------------------------------

On all platforms, wheels which depend on external shared libraries usually need
post-processing to make them usable on machines other than the one on which
they were built. This is because the RPATH entry for an external shared library
contains a path specific to the build machine. This post-processing is done by
tools like ``auditwheel`` (Linux), ``delvewheel`` (Windows), ``delocate``
(macOS) or ``repair-wheel`` (any platform, wraps the other tools).

Running any of those tools on a wheel produced by ``meson-python`` will vendor
the external shared library into the wheel and rewrite the RPATH entries (it
may also do some other things, like symbol mangling).

On Windows, the package author may also have to add the preloading like shown
above with ``_load_sharedlib()`` to the main ``__init__.py`` of the package,
``delvewheel`` may or may not take care of this (please check its documentation
if your shared library goes missing at runtime).


Using libraries from a Meson subproject
=======================================

TODO

- describe ``--skip-subprojects`` install option and why it's usually needed
- describe how to default to a static library and fold it into an extension module
- write and link to a small example project (also for internal and external
  shared libraries; may be a package in ``tests/packages/``)
- what if we really have a ``shared_library()`` in a subproject which can't be
  built as a static library?

    - this works on all platforms but Windows (for the same reason as internal
      shared libraries work on all-but-Windows)
    - one then actually has to install the *whole* subproject, which is likely
      to include other (unwanted) targets. It's possible to restrict to the
      ``'runtime'`` install tag, but that may still install for example an
      ``executable()``.

- mention the more complex case of an external dependency with a subproject as
  a fallback


