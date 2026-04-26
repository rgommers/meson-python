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
        pyproject_toml = os.path.join(os.path.dirname(__file__), 'pyproject.toml')
        with open(pyproject_toml) as f:
            data = f.readlines()

        version_line = next(
            line for line in data if line.startswith('version =')
        )
        version = version_line.strip().split(' = ')[1]
        return version.replace('"', '').replace("'", '')


    if __name__ == "__main__":
        print(get_version())


Obtaining the git commit hash and storing it inside your package
----------------------------------------------------------------

Capturing the git commit hash alongside the version is useful for bug
reports and reproducibility: the user can print ``mypkg.__version__`` and
``mypkg.__git_hash__`` to identify exactly which commit they are running.
The commit hash is not part of ``pyproject.toml`` and cannot be derived
from a source distribution after the fact, so it has to be written into
the package at build time.

The pattern used by NumPy and other large projects is a single helper
script that does double duty: it prints the version when called from
``project()``, and it writes a generated ``_version.py`` file containing
both the version and the git hash when called from a build step. The
script is wired up via :samp:`custom_target` for normal builds and via
:samp:`meson.add_dist_script` so that the generated file is also included
in source distributions.

In ``meson.build``:

.. code-block:: meson

    project(
        'mypkg',
        version: run_command(
            ['generate_version.py', '--print-version'],
            check: true,
        ).stdout().strip(),
    )

    py = import('python').find_installation()

    version_gen = files('generate_version.py')

    custom_target(
        'write_version_file',
        output: '_version.py',
        command: [py, version_gen, '-o', '@OUTPUT@'],
        build_by_default: true,
        build_always_stale: true,
        install: true,
        install_dir: py.get_install_dir() / 'mypkg',
    )

    meson.add_dist_script(py, version_gen, '-o', 'mypkg/_version.py')

The ``build_always_stale: true`` flag ensures that the recorded hash is
refreshed every time the project is rebuilt, rather than being cached
from a previous build.

The helper script reads the version from ``pyproject.toml`` (so the
version still has a single source of truth) and resolves the git hash
via ``git rev-parse``, falling back to ``'unknown'`` when called outside
a checkout — for example when building from an extracted source
distribution:

.. code-block:: python

    #!/usr/bin/env python3
    import argparse
    import os
    import subprocess


    def get_version_from_pyproject():
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, 'pyproject.toml')) as f:
            for line in f:
                if line.startswith('version ='):
                    return line.split('=', 1)[1].strip().strip('\'"')
        raise RuntimeError('version not found in pyproject.toml')


    def get_git_hash():
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=here, capture_output=True, check=True, text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return 'unknown'
        return result.stdout.strip()


    def write_version_file(outfile, version, git_hash):
        if 'MESON_DIST_ROOT' in os.environ:
            outfile = os.path.join(os.environ['MESON_DIST_ROOT'], outfile)
        with open(outfile, 'w') as f:
            f.write(f"__version__ = '{version}'\n")
            f.write(f"__git_hash__ = '{git_hash}'\n")


    def main():
        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--print-version', action='store_true')
        group.add_argument('-o', '--outfile')
        args = parser.parse_args()

        version = get_version_from_pyproject()
        if args.print_version:
            print(version)
            return
        write_version_file(args.outfile, version, get_git_hash())


    if __name__ == '__main__':
        main()

The ``MESON_DIST_ROOT`` branch ensures that when the script is invoked
as a dist script, it writes the generated file into the staging
directory ``meson dist`` is preparing, so it is included in the source
distribution. See :ref:`sdist` for the surrounding context.

The package's ``__init__.py`` re-exports the generated symbols:

.. code-block:: python

    from mypkg._version import __git_hash__, __version__

A complete worked example lives at ``tests/packages/version-from-script``
in the meson-python source tree.


Derive version from latest git tag
----------------------------------

When the version is encoded in git tags rather than in source files, the
build system has to query git at configure time. The cost is that git
becomes a build-time dependency in development checkouts, and the
resolved version has to be captured statically when generating a source
distribution so installs from the sdist don't need git at all.

There are two common tools for this in the Python ecosystem,
``setuptools-scm`` and ``versioneer``. Both can be wired up to
meson-python by invoking them from ``meson.build`` to obtain the version
string passed to :samp:`project()`.


Using ``setuptools-scm``
~~~~~~~~~~~~~~~~~~~~~~~~

This is the approach used by Matplotlib. Declare ``setuptools-scm`` as a
build requirement and configure it via a ``[tool.setuptools_scm]`` table
in ``pyproject.toml``:

.. code-block:: toml

    [build-system]
    build-backend = 'mesonpy'
    requires = ['meson-python', 'setuptools-scm']

    [project]
    name = 'mypkg'
    dynamic = ['version']

    [tool.setuptools_scm]
    fallback_version = '0.0.0'
    local_scheme = 'no-local-version'

The ``fallback_version`` setting is what lets builds succeed when there
is no ``.git`` directory present — for example when building from a
source distribution. The ``local_scheme = 'no-local-version'`` setting
strips the ``+gXXXXXXX`` local-version segment that setuptools-scm
appends in checkouts that have commits past the latest tag, which is
useful for reproducible CI builds and for uploading to indexes that
reject local-version segments.

In ``meson.build``, invoke ``setuptools-scm`` to compute the version:

.. code-block:: meson

    project(
        'mypkg',
        version: run_command(
            ['get_version.py'],
            check: true,
        ).stdout().strip(),
    )

with a small wrapper script (``get_version.py``):

.. code-block:: python

    #!/usr/bin/env python3
    from setuptools_scm import get_version
    print(get_version())

A complete worked example lives at
``tests/packages/version-setuptools-scm`` in the meson-python source
tree.


Using ``versioneer``
~~~~~~~~~~~~~~~~~~~~

Pandas uses ``versioneer``. Versioneer's installation step generates a
``_version.py`` module that is committed to the project source tree and
which contains the full version-resolution logic. In a development
checkout it inspects ``git describe --tags``; in a source distribution
the version is baked into the same file at sdist time, so neither git
nor versioneer itself needs to be available at install time.

Configure versioneer in ``pyproject.toml``:

.. code-block:: toml

    [build-system]
    build-backend = 'mesonpy'
    requires = ['meson-python']

    [project]
    name = 'mypkg'
    dynamic = ['version']

    [tool.versioneer]
    VCS = 'git'
    style = 'pep440'
    versionfile_source = 'mypkg/_version.py'
    versionfile_build = 'mypkg/_version.py'
    tag_prefix = 'v'

Run ``versioneer install`` once to generate ``mypkg/_version.py`` and
the accompanying ``.gitattributes`` rules; commit the result. From then
on, ``meson.build`` only has to import the generated module to get the
version:

.. code-block:: meson

    project(
        'mypkg',
        version: run_command(
            ['get_version.py'],
            check: true,
        ).stdout().strip(),
    )

with a small wrapper script:

.. code-block:: python

    #!/usr/bin/env python3
    from mypkg._version import get_versions
    print(get_versions()['version'])

A complete worked example lives at ``tests/packages/version-versioneer``
in the meson-python source tree.


Choosing between the two
~~~~~~~~~~~~~~~~~~~~~~~~

Both tools cover the same use case. ``setuptools-scm`` is lighter to
adopt — there is nothing to vendor — but it remains a build-time
dependency forever. ``versioneer`` is heavier up-front because it
vendors a generated ``_version.py`` (and optionally ``versioneer.py``)
into the source tree, but the resulting package has no runtime or
build-time dependency on versioneer itself, which is convenient for
projects that want to minimise their build environment.
