# RPATH CI results

## Local validation: additional ELF tag combinations

These four packages were added after the CI runs below. The following results
are local Linux aarch64 checks with Python 3.12, the Conda GCC toolchain, and
Meson 1.11.2, using the same three backend implementations. They are not CI
results, and the new packages have not yet run on x86_64.

| Package | main | PR rewrite | Astra |
| --- | --- | --- | --- |
| `rpath-elf-both-tags` | Retains build-only RUNPATH entry | Pass | Pass |
| `rpath-elf-both-tags-empty-runpath` | Pass | Pass | Pass |
| `rpath-elf-mixed-rpath-runpath` | Retains build-only path | Converts executable RPATH to RUNPATH | Pass |
| `rpath-elf-mixed-runpath-rpath` | Retains build-only path | Converts middle-library RPATH to RUNPATH | Pass |

All four also pass against Astra with Meson 1.9.2 and 1.12.0. Each comparison
asserts the input tags, builds two wheels, inspects both, and runs the installed
smoke test after deleting source and build directories. The mixed-chain rewrite
failures are header failures; those native smoke commands still succeed.

As a separate fixture check, removing RUNPATH from copies of Astra's two
dual-tag wheel executables makes the RPATH library load instead. The nonempty
case changes from success to returning the wrong value. The empty case changes
from the expected missing-library diagnostic to executing the ignored library;
its smoke assertion rejects that change. This verifies the negative loader test
is sensitive to reactivating RPATH.

The full Astra package suite with Meson 1.11.2 reports **22 passed, 1 failed,
3 skipped**. The failure remains `sharedlib-in-package-orig`, which loses
`$ORIGIN/sub`; all four additions pass. Lint and whitespace checks pass.
System-compiler validation could not run locally because `/usr/bin/cc` is not
installed; the existing CI matrix will cover that toolchain. The matrix gains
four packages within existing Linux jobs, with no additional jobs.

## Latest run: bounded GridFire builds

Sources: [package run 34963573037](https://github.com/rgommers/meson-python/actions/runs/34963573037)
and [downstream run 34963572962](https://github.com/rgommers/meson-python/actions/runs/34963572962),
both using suite commit `f95b65b5196d4c20c36d8ab9f529c07d55a0a12c`.
The compared backends remain main `cbe2ac4`, PR rewrite `2a2a7ae`, and
Astra `5bda04e`.

Every per-package outcome in all 48 jobs matches the previous run below
(8 green, 40 red). The existing package matrix and defect analysis therefore
still apply. Downstream job totals are also unchanged (3 green, 5 red), but
GridFire now provides useful macOS wheel evidence.

### GridFire: builds, headers, and imports

| Platform / result | main | PR rewrite | Astra |
| --- | --- | --- | --- |
| Linux wheel build | Timeout, 20 min | Timeout, 20 min | Timeout, 20 min |
| Linux last reported build progress | 419/615 | 415/615 | 406/615 |
| macOS wheel build | Completed, 16m 31s | Completed, 14m 25s | Completed, 17m 25s |
| macOS binaries with duplicate LC_RPATH findings | 17 | 0 | 0 |
| macOS retained-build-path findings requiring review | 15 | 15 | 15 |
| macOS installed-wheel smoke | Import fails | Import fails | Import fails |

The Linux job no longer silently consumes the whole 90-minute job limit.
Each backend reaches its own 1,200-second build deadline, terminates, and lets
the next comparison run. All three backends were attempted and the logs were
uploaded. Live output and the command-runner tests worked on both platforms.
There is still no Linux GridFire wheel or runtime result.

On macOS, main's `gridfire` extension contains nine copies of
`@loader_path/.gridfire.mesonpy.libs`; its `fourdst` extension contains five.
The relocated `libgridfire.dylib` contains eight copies of `@loader_path/.`.
The rewrite and Astra eliminate all 17 duplicate findings. This is real-world
evidence for the distinct-build-paths-to-one-wheel-path fix, consistent with
`rpath-relocated-multiple`. It does not resolve the separate duplicate cases
that still fail in the package suite.

All three installed-wheel imports fail with
`ModuleNotFoundError: No module named 'fourdst.constants'`, followed by
`ImportError: initialization failed`. This is a Python module-resolution
failure, not the missing-dylib error seen for VapourSynth and DWave. The likely
cause is an upstream packaging collision: the CI installation logs include both
`fourdst.cpython-312-darwin.so` and `fourdst/__init__.py`. In the pinned source,
the latter is empty, while the extension defines the `constants` submodule
that GridFire imports. A local Python import-resolution check confirms that a
package with `__init__.py` takes precedence over a same-name extension in the
same directory. The installed macOS wheel has not been independently rerun to
verify that diagnosis. Successful wheel builds must not be reported as
successful runtime tests.

The 15 remaining header findings on each backend all concern
`@loader_path/.` in relocated SUNDIALS libraries. These may be checker false
positives: that path points to sibling libraries in `.gridfire.mesonpy.libs`,
but also matches a path recorded in the original build metadata. The checker
currently compares path strings without distinguishing these two uses.
These findings require dependency-level inspection before being attributed to
a backend defect; the expectations and checker have not been weakened.

### Other downstream projects

The runtime conclusions are unchanged: NumPy linked against `scipy-openblas64`
passes with all three backends on both platforms, as does VapourSynth on Linux.
DWave passes on Linux with the rewrite and Astra; main still has 45 header
findings despite a successful smoke test.

On macOS, VapourSynth and DWave still import successfully with main and fail
with both the rewrite and Astra. Their literal `$ORIGIN` paths and missing
`@rpath` libraries remain the same compatibility regressions documented below.
The compiler-control correction removes the four compiler-path findings from
main's VapourSynth results (six retained-path findings become two), and the
two compiler-path findings from each alternative backend. It does not change
their two literal `$ORIGIN` findings or failing imports. DWave's macOS counts
remain 24 retained-build-path findings on main and 25 literal `$ORIGIN`
findings on each alternative backend.

## Previous run: 15 September 2026

The remainder records the earlier run, including the GridFire setup failures
that the latest run has progressed beyond.

Sources: [package run 34941012358](https://github.com/rgommers/meson-python/actions/runs/34941012358)
and [downstream run 34941012377](https://github.com/rgommers/meson-python/actions/runs/34941012377),
both using suite commit `2e63cc03c6f913c7377dc04e688fdf76591266f3`.
All three backends were available: main `cbe2ac4`, PR rewrite `2a2a7ae`, and
Astra `5bda04e`. The checkout failures from the first run are resolved.

All 48 package jobs executed tests (8 green, 40 red). Of eight downstream jobs,
three were green; the other five include both real failures and GridFire setup
problems. The package suite uses ordinary assertions, so red jobs are expected
when comparing implementations with known defects.

## Package matrix

Cells are **passed / failed / skipped**. The macOS arm64 (`macos-14`) and Intel
(`macos-15-intel`) results agree for every package at every tested Meson version.
Version ranges select the available patch release within each series.

| Environment | Meson selection | main | PR rewrite | Astra |
| --- | --- | --- | --- | --- |
| Linux x86_64, system compiler | `~=1.5.0` | 6/4/12 | 10/0/12 | 10/0/12 |
| Linux x86_64, system compiler | `~=1.6.0` | 7/7/8 | 13/1/8 | 14/0/8 |
| Linux x86_64, system compiler | `~=1.8.0` | 7/7/8 | 13/1/8 | 14/0/8 |
| Linux x86_64, system compiler | `~=1.9.0` | 9/10/3 | 14/5/3 | 18/1/3 |
| Linux x86_64, system compiler | `==1.11.1` | 9/10/3 | 14/5/3 | 18/1/3 |
| macOS, arm64 and Intel | `~=1.5.0` | 6/4/12 | 10/0/12 | 10/0/12 |
| macOS, arm64 and Intel | `~=1.6.0` | 7/7/8 | 11/3/8 | 12/2/8 |
| macOS, arm64 and Intel | `~=1.8.0` | 7/7/8 | 11/3/8 | 12/2/8 |
| macOS, arm64 and Intel | `~=1.9.0` | 8/11/3 | 12/7/3 | 16/3/3 |
| macOS, arm64 and Intel | `==1.11.1` | 8/11/3 | 12/7/3 | 16/3/3 |
| Linux aarch64, Conda compiler | environment-resolved | 8/11/3 | 4/15/3 | 18/1/3 |

The Linux system compiler normally emits RUNPATH, while the Conda compiler emits
RPATH and adds its own search directory. This explains the much larger number of
PR failures with Conda: conversion from RPATH to RUNPATH is observable there even
when an import happens to succeed. The explicitly transitive ELF case detects
that change on both Linux toolchains.

### Per-package results with Meson 1.11.1

These are the actual test outcomes, without reclassifying or suppressing failures.
“Skip” means that the package targets the other platform. Main failures include
expectations for newer installation-metadata support; a failing main test alone
does not establish a regression introduced by the rewrite.

| Package | Linux main | Linux PR | Linux Astra | macOS main | macOS PR | macOS Astra |
| --- | --- | --- | --- | --- | --- | --- |
| `rpath-build-only-removal` | **Fail** | **Fail** | Pass | **Fail** | Pass | Pass |
| `rpath-elf-install-precedence` | Pass | **Fail** | Pass | Skip | Skip | Skip |
| `rpath-elf-rpath-transitive` | **Fail** | **Fail** | Pass | Skip | Skip | Skip |
| `rpath-elf-runpath-direct` | **Fail** | Pass | Pass | Skip | Skip | Skip |
| `rpath-in-package-flat` | Pass | Pass | Pass | Pass | Pass | Pass |
| `rpath-in-package-nested` | **Fail** | Pass | Pass | **Fail** | Pass | Pass |
| `rpath-install-build-overlap` | Pass | Pass | Pass | Pass | Pass | Pass |
| `rpath-install-multiple` | **Fail** | **Fail** | Pass | **Fail** | **Fail** | Pass |
| `rpath-ldflags` | **Fail** | Pass | Pass | **Fail** | Pass | Pass |
| `rpath-legacy-origin-flat` | Pass | Pass | Pass | Pass | **Fail** | **Fail** |
| `rpath-link-args-relative` | **Fail** | Pass | Pass | **Fail** | Pass | Pass |
| `rpath-macos-duplicates-remove` | Skip | Skip | Skip | **Fail** | **Fail** | Pass |
| `rpath-macos-duplicates-retain` | Skip | Skip | Skip | **Fail** | **Fail** | **Fail** |
| `rpath-macos-path-spaces` | Skip | Skip | Skip | **Fail** | **Fail** | Pass |
| `rpath-mixed-layout` | **Fail** | Pass | Pass | **Fail** | **Fail** | Pass |
| `rpath-no-dependencies` | Pass | Pass | Pass | Pass | Pass | Pass |
| `rpath-pkgconfig-absolute` | Pass | Pass | Pass | Pass | Pass | Pass |
| `rpath-pkgconfig-search` | Pass | Pass | Pass | Pass | Pass | Pass |
| `rpath-relocated-chain` | **Fail** | Pass | Pass | **Fail** | Pass | Pass |
| `rpath-relocated-multiple` | **Fail** | Pass | Pass | **Fail** | Pass | Pass |
| `rpath-relocated-single` | Pass | Pass | Pass | Pass | Pass | Pass |
| `sharedlib-in-package-orig` | Pass | **Fail** | **Fail** | Pass | **Fail** | **Fail** |

## Defects demonstrated by the package tests

### Original layouts stop loading

`sharedlib-in-package-orig` passes on main throughout the matrix. With the PR and
Astra, it fails on Linux starting with Meson 1.9: the extension retains `$ORIGIN`
but loses `$ORIGIN/sub`, and importing fails because `libexamplelib2.so` cannot
be found. On macOS, both backends fail starting with Meson 1.6: the extension
contains literal `$ORIGIN` instead of usable `@loader_path` paths, and dyld
cannot find `libexamplelib.dylib`.

The small `rpath-legacy-origin-flat` package reproduces the macOS compatibility
problem independently. These are runtime failures, not just differing headers.
The unchanged original fixture must remain unchanged to keep that evidence.

### Duplicate LC_RPATH handling is still incomplete

`rpath-relocated-multiple`, the case where distinct build paths map to one
`.mesonpy.libs` path, **passes on both PR and Astra**. Main fails it on macOS.
Thus the rewrite fixes this form of the issue, but not every duplicate case.

- `rpath-macos-duplicates-remove`: the PR passes duplicate `-delete_rpath`
  options in one `install_name_tool` invocation, which Apple rejects. Astra passes.
- `rpath-macos-duplicates-retain`: **all three backends leave both copies** of
  `@loader_path/dupa`. Astra's failure is not in its duplicate-removal loop: this
  fixture has no relocation or install/build RPATH metadata, so `_install_path()`
  never calls the RPATH handler. Deduplication inside that handler cannot repair
  a file the wheel builder skips.

The second finding comes from combining the observed duplicate output with the
backend's call-site condition; it is not an assumption about how Apple's tool
handles deletion.

### Installation lists, ordering, and repeat builds

- `rpath-install-multiple`: the PR retains duplicate `$ORIGIN/one` entries on
  Linux and writes one colon-containing LC_RPATH string on macOS instead of two
  commands. Astra passes.
- `rpath-build-only-removal`: on Linux the PR leaves an empty path entry after
  removing the build path. Astra removes the dynamic tag and passes.
- `rpath-elf-install-precedence`: the PR puts `external` before `private`; the
  executable selects the wrong same-SONAME library and returns failure.
- `rpath-elf-rpath-transitive`: the PR changes RPATH to RUNPATH; the executable
  cannot find the indirect `libleaf.so` dependency. Astra passes.
- `rpath-macos-path-spaces`: the PR's repeated wheel build attempts to add an
  already-present `@loader_path/new path/(library)` command. The parser loses
  the complete path, and `install_name_tool` rejects the duplicate addition.
- `rpath-mixed-layout`: the PR's repeated wheel build invokes
  `install_name_tool` with only the filename and no edit options. Apple rejects
  that no-op invocation. Astra passes both repeat-build cases.

## Downstream results

All projects use the same pinned source revision and Python dependency
constraints across the three backends within a job. “Pass” means the raw-wheel
header checker and installed-wheel smoke command both passed. No repair step ran.

| Project / platform | main | PR rewrite | Astra |
| --- | --- | --- | --- |
| NumPy + scipy-openblas64 / Linux | Pass | Pass | Pass |
| NumPy + scipy-openblas64 / macOS | Pass | Pass | Pass |
| VapourSynth / Linux | Pass | Pass | Pass |
| VapourSynth / macOS | Smoke passes; header flags | **Import fails**; header flags | **Import fails**; header flags |
| DWave / Linux | Smoke passes; header flags | Pass | Pass |
| DWave / macOS | Smoke passes; header flags | **Import fails**; header flags | **Import fails**; header flags |
| GridFire / Linux | Build fails | Build fails | Build fails |
| GridFire / macOS | Configure fails | Configure fails | Configure fails |

### Confirmed macOS loader failures

VapourSynth fails to load `@rpath/libvapoursynth.4.dylib` with both PR and Astra.
The extension's LC_RPATH contains literal `$ORIGIN`. DWave similarly fails to
load `@rpath/libdwave-optimization.dylib`; 25 extension modules are flagged for
literal `$ORIGIN` or `$ORIGIN/..`. Main's installed native smoke commands pass
for both projects. The `rpath-legacy-origin-flat` fixture now has two real-world
counterparts in CI.

### Header-only failures and a checker correction

On Linux, main's DWave wheel has 23 padding-entry flags (`XXXXXXX` or `XX`) and
22 retained-build-path flags. All three smoke tests pass, but only PR and Astra
pass the header checks.

The macOS VapourSynth checker also flags Conda's compiler search directories as
build-only paths. These need to be separated from project build paths: the small
package runner already measures and preserves compiler-injected paths, while
the downstream runner did not. Main has six retained-path flags, and PR/Astra
have two each in addition to their literal `$ORIGIN` and smoke failures.
Some of these flags concern the Conda library directory; others concern project
paths such as `@loader_path/`. They must not all be dismissed together.

The downstream runner now builds the dependency-free control with the same
backend and compiler before building the project, records `toolchain_paths`, and
exempts only those measured paths from build-only removal checks. Duplicate,
padding, literal `$ORIGIN`, forbidden source/build-directory, and runtime checks
remain active. This change does not make either failing macOS import acceptable.

### GridFire setup failures

The Linux failure occurs while compiling minizip-ng: Meson finds system zlib 1.3
and adds `-I/usr/include` to a Conda compiler command. Host and Conda sysroot
headers mix, ending with `fatal error: bits/timesize.h: No such file or directory`.
The environment had `libzlib` but not the `zlib` development package. The locked
native environment now includes zlib's headers and pkg-config file.

On macOS, Boost 1.92 is installed and Meson finds its include directory, but it
searches the Conda prefix's `lib/clang/21` rather than its `lib` directory, then
reports Boost missing. The driver now supplies `BOOST_INCLUDEDIR` and
`BOOST_LIBRARYDIR` from the active Conda prefix for GridFire, preserving explicit
user overrides. Neither failure reached wheel RPATH processing.

Local validation progressed past those issues and exposed a further build issue:
the pinned liblogging subproject uses pthread functions without linking pthread.
The Conda sysroot's older glibc requires explicit linkage. The GridFire driver now
adds `-pthread` to Linux C++ compilation and linking flags for all three backends;
this changes neither the source nor the requested RPATH layout.

## Scope of the follow-up

These changes adjust the diagnostic runner and GridFire build environment only.
The fixture expectations, original fixture contents, production code, and three
backend revision pins remain unchanged. Native macOS execution of the corrected
GridFire setup and compiler-path control still requires another CI run.

Local validation of the updated downstream runner passed with DWave and Astra:
all 26 native binaries and the installed model smoke test passed, and the report
recorded the independently measured Conda compiler path. Targeted checker checks
confirmed that exempting this path does not suppress duplicate compiler paths,
linker padding, or actual source/build paths. Ruff and whitespace checks passed.

Local Linux aarch64 validation found Conda zlib 1.3.2 and Boost 1.92, confirmed
that minizip's compile command no longer includes `/usr/include`, and compiled
and linked minizip, liblogging, and libplugin with the corrected setup. Upstream
wrap archives were cached from their GitHub mirrors and verified against the
wrap-file hashes because direct WrapDB/GitLab downloads were unreachable. The
remaining full GridFire build was stopped: the pinned project repeats its core
sources across many targets (615 build commands in this configuration). Its
complete wheel build and installed import still need CI; this is not a local
GridFire pass.

The downloaded job logs and parsed matrix are stored under
`/tmp/rpath-ci-review/`. This analysis uses the detailed errors now printed in
those logs; it does not rely on successfully downloading wheel artifacts.
