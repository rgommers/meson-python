.. SPDX-FileCopyrightText: 2023 The meson-python developers
..
.. SPDX-License-Identifier: MIT

.. _how-to-guides-dynamic-versioning:

******************
Dynamic versioning
******************

Things a package author may want:

1. Use the package version in a ``meson.build`` file without duplicating the version string between ``pyproject.toml`` and ``meson.build``.
2. Use the hash of the current commit in the package version, or store it in a configuration file.
3. Derive the version from the most recent git tag rather than maintain it in the code.

.. note::

    Each of these things has a cost - keeping all metadata static and not
    running ``git`` as part of the build avoids running extra build steps in
    some cases. Only use these dynamic features if you have a good reason to do
    so!

Single-sourcing the version string
----------------------------------

When you want to define your project's version string in a single place,
``meson-python`` knows how to extract the version number from the ``project()``
call in the top-level ``meson.build``; in ``pyproject.toml`` it can be declared
as dynamic:

.. code-block:: toml

    [project]
    dynamic = ['version']

Then in ``meson.build``, define the version:

.. code-block:: meson

   project('my-project', 'c', version: '1.2.3')

It can also be done the other way around - this requires a bit more code,
however it has the advantage that all metadata remains static in
``pyproject.toml``, which can in some cases avoid triggering a build
when an installer needs to obtain the version. To implement this,
set the version in ``pyproject.toml``:

.. code-block:: toml

    [project]
    version = '1.2.3'

And in ``meson.build``, run a helper script as part of the project call
(again, this is only needed if you actually use the version string inside a
``meson.build`` file):

.. code-block:: meson

    project('my-project',
        'c',
        version: run_command('get_version.py', check: true).stdout().strip(),
    )

With that ``get_version.py`` script retrieving the version from
``pyproject.toml``:

.. code-block:: python

    #!/usr/bin/env python3
    import os

    def get_version():
        pyproject_toml = os.path.join(os.path.dirname(__file__), '../../pyproject.toml')
        with open(pyproject_toml) as f:
            data = f.readlines()

        version_line = next(
            line for line in data if line.startswith('version =')
        )
        version = version_line.strip().split(' = ')[1]
        return = version.replace('"', '').replace("'", '')


    if __name__ == "__main__":
        print(get_version())


Obtaining the git commit hash and storing it inside your package
----------------------------------------------------------------



Derive version from latest git tag
----------------------------------
