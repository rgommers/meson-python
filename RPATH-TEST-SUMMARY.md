# RPATH regression package expectations

This document collects the expectations for the 21 standalone `rpath-*` packages
and the unchanged `sharedlib-in-package-orig` compatibility fixture. It describes
the **raw wheels produced by meson-python**, before auditwheel or delocate repair.
The tests build native code, inspect the installed binaries, and require that the
installed wheel works after its source and build directories are removed. Known
bugs are ordinary failures, not xfails.

## How to read the expectations

Each table lists project path entries, in addition to any compiler-injected paths
measured independently using the dependency-free control. Those compiler paths
must survive when present in the input binary. “None” means no project paths;
when no paths at all remain, the ELF RPATH/RUNPATH tag must also disappear.

Every listed path must occur once. Raw entries are checked for duplicates before
normalization; empty entries and linker padding consisting of `X` characters are
rejected. Equivalent spellings such as `$ORIGIN/.` and `$ORIGIN` are accepted,
but meaningful whitespace is preserved.

On Linux, path entries belong to `DT_RPATH` or `DT_RUNPATH`. Except where a test
explicitly specifies the tag, the wheel must preserve the input tag type. On
macOS, each path is a separate `LC_RPATH` load command: two directories mean two
commands, not one command containing a colon-separated string. Retained macOS
commands need not be reordered. Only the ELF precedence test requires a
particular order.

For compactness, the tables use these substitutions:

- `D` is the wheel's relocated-library directory, named
  `.<distribution_name_with_underscores>.mesonpy.libs`, beside `probe/`.
  For example, in `rpath-relocated-multiple`, `$ORIGIN/../D` expands to
  `$ORIGIN/../.rpath_relocated_multiple.mesonpy.libs`.
- `E` is the absolute external prefix created by the test. It remains available
  during the raw-wheel smoke test; it is not a source or build directory.
- The extension is `probe/_probe<ABI suffix>.so` unless stated otherwise.
  Library names below omit the platform suffix (`.so` or `.dylib`).

The listed Meson versions are minimum versions for running each case. Before
Meson 1.9, the runner additionally allows paths present in the original binary,
because the newer build-path removal metadata is unavailable. Required paths,
duplicate checks, tag checks, and successful execution still apply. With Meson
1.9 or newer, unlisted project paths and build-only paths must be removed.

## Relocation and package layouts

Package names below link to their detailed README. Unless a library exception is
listed afterward, all libraries shipped by these cases must have no project paths.

| Package and scenario | Minimum Meson | Linux extension paths | macOS extension LC_RPATH paths |
| --- | --- | --- | --- |
| [rpath-no-dependencies](tests/packages/rpath-no-dependencies/README.md): extension without project libraries; also measures toolchain paths | 0.64 | None | None |
| [rpath-relocated-single](tests/packages/rpath-relocated-single/README.md): one library moved into `D` | 0.64 | `$ORIGIN/../D` | `@loader_path/../D` |
| [rpath-relocated-multiple](tests/packages/rpath-relocated-multiple/README.md): two libraries from different build directories moved into the same `D`; issue #813 | 0.64 | `$ORIGIN/../D`, once | `@loader_path/../D`, one command |
| [rpath-relocated-chain](tests/packages/rpath-relocated-chain/README.md): extension → first → second, both libraries in `D` | 0.64 | `$ORIGIN/../D` | `@loader_path/../D` |
| [rpath-in-package-flat](tests/packages/rpath-in-package-flat/README.md): extension → sibling first, using a platform-correct install path | 1.6 | `$ORIGIN` | `@loader_path` |
| [rpath-in-package-nested](tests/packages/rpath-in-package-nested/README.md): extension → sibling first → sub/second | 1.6 | `$ORIGIN` | `@loader_path` |
| [rpath-mixed-layout](tests/packages/rpath-mixed-layout/README.md): extension → two relocated libraries and an in-package private library | 1.6 | `$ORIGIN/private`, `$ORIGIN/../D` | `@loader_path/private`, `@loader_path/../D` |
| [rpath-legacy-origin-flat](tests/packages/rpath-legacy-origin-flat/README.md): historical literal `$ORIGIN` install path, including on macOS | 0.64 | `$ORIGIN` | Usable native anchor `@loader_path` |

The chain cases also check the library that loads another library:

| Package / installed library | Linux paths | macOS LC_RPATH paths |
| --- | --- | --- |
| `rpath-relocated-chain`: `D/libfirst` | `$ORIGIN/.` | `@loader_path/.` |
| `rpath-in-package-nested`: `probe/libfirst` | `$ORIGIN/sub` | `@loader_path/sub` |

Their `libsecond` libraries have no project paths. These cases catch a backend
that repairs the extension but leaves a library unable to find its own dependency.
The legacy case requires a working import and a usable native path on macOS;
retaining literal `$ORIGIN` there is not accepted as a successful compatibility
result.

## User paths and Meson installation metadata

| Package and scenario | Minimum Meson | Linux extension paths | macOS extension LC_RPATH paths |
| --- | --- | --- | --- |
| [rpath-link-args-relative](tests/packages/rpath-link-args-relative/README.md): intentional relative path from target `link_args`, alongside relocation | 0.64 | `$ORIGIN/user`, `$ORIGIN/../D` | `@loader_path/user`, `@loader_path/../D` |
| [rpath-ldflags](tests/packages/rpath-ldflags/README.md): relative and absolute paths from `LDFLAGS`, alongside relocation | 0.64 | `$ORIGIN/user`, `E`, `$ORIGIN/../D` | `@loader_path/user`, `E`, `@loader_path/../D` |
| [rpath-pkgconfig-absolute](tests/packages/rpath-pkgconfig-absolute/README.md): `.pc` supplies an absolute library filename and RPATH, like scipy-openblas64 | 0.64 | `E/lib` | `E/lib` |
| [rpath-pkgconfig-search](tests/packages/rpath-pkgconfig-search/README.md): `.pc` supplies conventional `-L`/`-l` flags and RPATH | 0.64 | `E/lib` | `E/lib` |
| [rpath-install-multiple](tests/packages/rpath-install-multiple/README.md): `install_rpath` contains one:two:one | 1.6 | `$ORIGIN/one`, `$ORIGIN/two` | `@loader_path/one`, `@loader_path/two` as separate commands |
| [rpath-install-build-overlap](tests/packages/rpath-install-build-overlap/README.md): same path in build and install metadata | 1.9 | `$ORIGIN/keep`, once | `@loader_path/keep`, once |
| [rpath-build-only-removal](tests/packages/rpath-build-only-removal/README.md): remove build-only path, empty install path | 1.9 | None; no empty/padding tag | None |

In `rpath-link-args-relative`, relocated `libfirst` has no project paths. In
`rpath-ldflags`, the same flags affect `D/libfirst`, which must retain
`$ORIGIN/user`, `E`, and `$ORIGIN/.` on Linux, or `@loader_path/user`, `E`, and
`@loader_path/.` on macOS. This explicitly checks the relocated library as well
as the extension.

The pkg-config cases build a real local provider outside the source/build trees.
The provider is not bundled in the wheel. These cases require preservation of
its absolute path, not replacement with a meson-python private-library path.
Together with the linker-flag cases, they distinguish intentional user paths
from temporary build paths. The install/build overlap case checks that an
explicit installation request wins over removal of the same build path.

## macOS load-command edge cases

These packages require macOS and Meson 1.9 or newer; Linux skips them. Each builds
an extension without project-library dependencies.

| Package | Input and expected extension LC_RPATH commands |
| --- | --- |
| [rpath-macos-duplicates-retain](tests/packages/rpath-macos-duplicates-retain/README.md) | Start with two `@loader_path/dupa` commands; retain exactly one. |
| [rpath-macos-duplicates-remove](tests/packages/rpath-macos-duplicates-remove/README.md) | Start with two build-only `@loader_path/dupa` commands; remove both. No project commands remain. |
| [rpath-macos-path-spaces](tests/packages/rpath-macos-path-spaces/README.md) | Retain `@loader_path/some path/(library)` and `@loader_path/trailing ` (one trailing space); add `@loader_path/new path/(library)`; remove `@loader_path/remove this (build)`. Each retained/added string occurs exactly once. |

The duplicate inputs are real Mach-O files: a Meson custom target replaces an
equal-length seed path after linking. The runner confirms two duplicate input
commands before wheel processing. No meson-python RPATH helper is mocked or
called directly. The whitespace case checks complete path strings, including
parentheses and trailing whitespace, to expose lossy parsing of `otool` output.

## Linux loader semantics

These three packages use installed **executables** (`probe/probe-exe`), rather
than extension modules, so the loader behavior is exercised directly. They
require Linux and Meson 1.9 or newer; macOS skips them.

| Package | Executable paths and tag | Library paths and runtime expectation |
| --- | --- | --- |
| [rpath-elf-install-precedence](tests/packages/rpath-elf-install-precedence/README.md) | `$ORIGIN/private` before `$ORIGIN/external`; preserve input tag type | Both copies of `libchoice` have no project paths. They share a SONAME but return different values: the installed private choice must produce 42, not 7. |
| [rpath-elf-rpath-transitive](tests/packages/rpath-elf-rpath-transitive/README.md) | `DT_RPATH` containing `$ORIGIN/lib` | `probe/lib/libmiddle` and `libleaf` have no project paths. The executable's transitive RPATH must resolve middle → leaf. Changing it to RUNPATH breaks this. |
| [rpath-elf-runpath-direct](tests/packages/rpath-elf-runpath-direct/README.md) | `DT_RUNPATH` containing `$ORIGIN/lib` | `probe/lib/libmiddle` needs `$ORIGIN` for its own leaf dependency; `libleaf` has no project paths. Preserve the middle library's input tag type. Execution must succeed with direct-dependency search semantics. |

## Unchanged compatibility fixture

[sharedlib-in-package-orig](tests/packages/sharedlib-in-package-orig) preserves the
original fixture's contents byte for byte. Its assertions and smoke code live
outside the package so the fixture itself stays unchanged. It runs with Meson
0.64 or newer.

| Installed binary | Linux paths | macOS LC_RPATH paths |
| --- | --- | --- |
| `mypkg/_example<ABI suffix>.so` | `$ORIGIN`, `$ORIGIN/sub` | `@loader_path`, `@loader_path/sub` |
| `mypkg/libexamplelib` | None | None |
| `mypkg/sub/libexamplelib2` | None | None |

Both native operations must work: `example_sum(2, 5) == 7` and
`example_prod(6, 7) == 42`. The Windows run checks successful execution only,
without inspecting RPATH headers. This fixture deliberately preserves historical
inputs, including literal `$ORIGIN` syntax, and demands continued functionality.
It is a separate compatibility check from the new platform-correct layouts.

## What every package run verifies

1. Build the native input with the selected backend and capture its headers and
   Meson's installation metadata before wheel postprocessing.
2. Build and inspect two wheels using the same build directory. Both must meet
   the path expectations, and their path lists, counts, and tag types must agree.
3. Remove source and build directories, install into a fresh virtual environment,
   clear `PYTHONPATH`, `LD_LIBRARY_PATH`, `DYLD_LIBRARY_PATH`, and
   `DYLD_FALLBACK_LIBRARY_PATH`, then execute the package's smoke test.
4. Save input/output headers, commands, metadata, and failures in JSON reports.
   Every installed native binary must match an expectation rule.

Run the suite from the repository root with a native compiler, Meson, Ninja,
`build`, pytest, and the backend's dependencies available:

```sh
python -m pytest tests/test_rpath_packages.py -v
```

Set `MESONPY_RPATH_BACKEND` to compare another backend checkout and
`MESONPY_RPATH_REPORT_DIR` to retain reports. Each package README also gives its
individual test command and any manual preparation steps.

The [runner guide](tools/rpath-validation/README.md) covers the separate pinned
NumPy/scipy-openblas64, GridFire, VapourSynth, and DWave builds and CI comparisons.
Those complement these small packages; they do not replace their exact header
expectations. This document states the test contract, not the outcome of the
currently running CI. No universal-binary coverage is included.
