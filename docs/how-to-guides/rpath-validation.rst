.. SPDX-FileCopyrightText: 2026 The meson-python developers
..
.. SPDX-License-Identifier: MIT

Validating RPATH changes
========================

Run the focused regression suite with:

.. code-block:: console

   $ python -m pytest tests/test_rpath.py tests/test_wheel.py -k 'rpath or local_lib or sharedlib_in_package or link_library_in_subproject'

The dedicated CI job covers Meson 1.5, 1.6, 1.8, 1.9, and the current release
on Linux and macOS, with an additional Intel macOS job. The Pixi job covers
compiler-injected external paths. Native macOS tests exercise duplicate load
commands, paths containing spaces and parentheses, and universal binaries
with different paths in each architecture. ELF tests check both dynamic tags,
indirect dependency loading, and explicit installation search precedence.

The ``rpath-mixed-layout`` package combines two relocated libraries in
different build directories with a library inside the Python package. Its
test builds twice, checks every native file for duplicates, removes the build
directory, and exercises the installed extension in a fresh interpreter.

The macOS anchor compatibility test deliberately checks the current literal
``$ORIGIN`` behavior. With Meson before 1.9, coincident build and installation
layouts can load through retained ``@loader_path`` entries. With Meson 1.9 or
later those entries are removed and importing fails. This characterization
does not implement an anchor translation policy.

Downstream checks
-----------------

Use Python 3.12 and a separate build environment for each project. Install the
project's native toolchain, build requirements, and runtime dependencies, then
install the checkout of ``meson-python`` under review. Keep the Meson version
fixed for a comparison. SciPy 1.15.1 and D-Wave Optimization have backend bounds
which must be deliberately overridden for these diagnostic builds; do not
interpret the overridden build as normal dependency resolution.

.. code-block:: console

   $ python -m pip install --no-deps /path/to/meson-python
   $ python -c 'import mesonpy; print(mesonpy.__file__)'
   $ python -m build --wheel --no-isolation --skip-dependency-check -Cbuild-dir=build-rpath

Build the same downstream revision with the branch base and the changed backend
in separate clean build directories. Record all dependency versions using
``python -m pip freeze`` and the compiler version. Pin the source commit resolved
at the start of the check, including submodule revisions. The following projects
exercise different cases:

.. list-table::
   :header-rows: 1
   :widths: 23 42 35

   * - Project / revision
     - Purpose
     - Smoke test
   * - `GridFire <https://github.com/tboudreaux/GridFire/tree/56f93420527912cf94da1d52bd0d5c32bd0311a9>`_, ``56f934205279``
     - Original duplicate RPATH report; many relocated dependencies.
     - Import ``gridfire`` and run its upstream Python smoke tests.
   * - `VapourSynth <https://github.com/vapoursynth/vapoursynth>`_, current master
     - Current unbounded backend dependency with literal ``$ORIGIN``.
     - Import ``vapoursynth`` and evaluate ``core.std.BlankClip().get_frame(0)``.
   * - `SciPy <https://github.com/scipy/scipy>`_, v1.15.1
     - Historical ``libsf_error_state`` inside the Python package.
     - Run ``scipy.special`` error-state tests and evaluate a special function.
   * - `D-Wave Optimization <https://github.com/dwavesystems/dwave-optimization>`_, current main
     - Shared library used by nested extensions with ``$ORIGIN/..``.
     - Construct a ``Model``, create a binary variable, and import its symbols.
   * - `chromo <https://github.com/impy-project/chromo>`_, current main
     - Control using platform-specific anchors and an internal Pythia library.
     - Enable Pythia8 and run the project's Pythia8 smoke tests.

The GridFire revision above is from the date of the duplicate-path report.
Its configuration builds the shared dependencies needed for the regression.
The current main branch instead defaults to static libraries and skips
installing subprojects, so it is not a substitute for this historical case.

For the literal-anchor projects, repeat with only the installation anchors
changed to ``@loader_path`` on macOS. Retain the patch in the report. Run with
Meson 1.8 and 1.9 where the project's own requirements permit it; report any
additional requirement override rather than silently changing it.

Inspect raw wheels before running any repair tool. The repository includes a
checker which records all native files' RPATHs (per architecture on macOS),
duplicate and forbidden paths, source/backend revisions and patches, and a
fresh-environment smoke test:

.. code-block:: console

   $ python /path/to/meson-python/tools/check-wheel-rpaths.py dist/package.whl --source . --forbid /absolute/path/to/build-rpath --smoke 'import package; package.exercise_native_code()' --report raw-rpaths.json

Replace the wheel filename and smoke code with the project's actual artifact
and a test exercising its native dependencies. Also forbid relative build paths
from ``intro-install_plan.json``'s ``build_rpaths`` when they are not intentional
``install_rpath`` entries. Move the project build directory out of its original
location before invoking the checker, so leftover paths cannot mask failures.
The checker removes loader environment overrides, runs outside the source tree,
and uses a new virtual environment inheriting installed runtime dependencies.
It does not install missing runtime dependencies automatically.

Repeat after the project's normal ``delocate`` or ``auditwheel`` repair process,
writing a separate report. For the repaired wheel, additionally make external
build-time library prefixes unavailable. Successful repair does not excuse a
failure in a raw wheel that should load in its original dependency environment.

Keep raw and repaired reports, source patches, compiler/dependency versions,
build logs, and upstream test results together. Native macOS results and
downstream builds must be recorded as pending until they have actually run;
mocked command checks are not substitutes for loader tests.
