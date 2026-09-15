# RPATH CI results: second run, 15 September 2026

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
