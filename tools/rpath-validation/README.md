# RPATH package and downstream comparisons

This is a diagnostic suite for discussing the RPATH rewrite. Failures are normal
assertion failures, including compatibility regressions; there are no xfails.
No production changes are included in the test-suite commits.

The standalone [package expectation summary](../../RPATH-TEST-SUMMARY.md) collects
all cases, including Linux tags, macOS load-command counts, and secondary-library
paths.

## Reading the runners

`tests/test_rpath_packages.py` builds the small packages and compares each wheel
against its package's `expectations.json`. `tests/rpath_inspection.py` contains the
shared, standard-library-only binary inspector, which uses `readelf` or `otool`
independently of the backend under test.

`run.py` checks out and builds a downstream project, then installs and exercises
its wheel. Its `check_paths()` function collects header problems separately from
the build/install flow, so header failures do not prevent the runtime check.
It imports the shared inspector directly and does not need to import pytest.
The dependency-free control measures compiler RPATHs before each downstream
build, so the checker preserves those paths while still rejecting project build
paths, duplicates, padding, and unusable macOS `$ORIGIN` entries.

## Start with the small packages

From the repository root, with a C compiler, Meson, Ninja, `build`, `pytest`, and
the backend's Python dependencies installed:

```sh
python -m pytest tests/test_rpath_packages.py -vv
python -m pytest tests/test_rpath_packages.py -k pkgconfig_absolute -vv
```

Linux requires `readelf` and `patchelf`; macOS requires Xcode's `otool` and
`install_name_tool`. Universal binaries are outside this suite's scope.

Every `tests/packages/rpath-*` directory contains a real standalone package,
its build/install topology, platform-specific header expectations, and a native
smoke test. `expectations.json` records the assertions used by the runner.
The runner never calls the backend's RPATH helpers to inspect output. It uses
`Project` only to configure and compile the input, then builds wheels through
the PEP 517 frontend. Dependency checking is disabled for that frontend because
the chosen backend is imported directly from its checkout, not necessarily
installed as distribution metadata.

Each package is copied to a temporary directory. The runner captures input
headers and Meson installation metadata, builds twice in one build directory,
inspects both wheels, removes the source/build trees, and runs the installed
wheel in a fresh environment. It removes Python-path and loader-path overrides.
External provider prefixes intentionally remain available. The pkg-config
fixtures build their own providers locally; no external source download is
needed for the small packages.

Paths are checked per binary. Duplicate counting precedes normalization of
Meson's equivalent `$ORIGIN` and `$ORIGIN/` spellings. Linux checks the actual
`DT_RPATH`/`DT_RUNPATH` tag as well as entries. macOS counts `LC_RPATH` commands
and preserves complete whitespace-containing paths. An independently built
no-dependency control identifies legitimate compiler-injected paths.

## Preserve the historical fixture

`tests/packages/sharedlib-in-package-orig` is byte-for-byte the tracked package
from `cbe2ac4`. Its containing directory is renamed; its project name, C sources,
Python imports, Meson layout, and literal `$ORIGIN` are unchanged. No README or
expectations file was added inside that preserved tree.

Its expectations live in `tests/rpath-original-expectations.json` and its smoke
test in `tests/rpath-original-smoke.py`. The extension must reach both the
library beside it and the library in `mypkg/sub`; both original functions must
work. Linux needs usable `$ORIGIN` and `$ORIGIN/sub` paths, and macOS needs usable
`@loader_path` and `@loader_path/sub` paths. Windows checks imports and native
results without RPATH assertions.

Successful imports remain the compatibility requirement even when previous
success depended on retained build paths. This makes a backwards-incompatible
change visible without prescribing a production fix or changing the original
fixture to use different anchors. With Meson 1.9+, the current rewrite loses the
second library's path on Linux as well as exposing the macOS anchor problem.

## Compare backend revisions

Use the same interpreter, compiler environment, and Meson version for each run:

```sh
git worktree add --detach /tmp/backend-main cbe2ac4
git worktree add --detach /tmp/backend-pr 2a2a7ae
git worktree add --detach /tmp/backend-astra 5bda04e

MESONPY_RPATH_BACKEND=/tmp/backend-main MESONPY_RPATH_REPORT_DIR=/tmp/rpath-reports/main python -m pytest tests/test_rpath_packages.py -vv
MESONPY_RPATH_BACKEND=/tmp/backend-pr MESONPY_RPATH_REPORT_DIR=/tmp/rpath-reports/pr python -m pytest tests/test_rpath_packages.py -vv
MESONPY_RPATH_BACKEND=/tmp/backend-astra MESONPY_RPATH_REPORT_DIR=/tmp/rpath-reports/astra python -m pytest tests/test_rpath_packages.py -vv
```

Reports contain complete build commands and output, input headers, installation
metadata, both wheels' headers, and assertion/runtime failures. Tests still run
the smoke check when header assertions fail. A failed build is reported as a
build failure, not as a successful RPATH check.

Routine CI compares Meson `~=1.9.0` and `~=1.12.0`: 1.9 exercises all
platform-applicable RPATH cases, and 1.12 covers the current release series.
This gives 18 system-compiler jobs plus three Conda-compiler jobs, down from 48.
The completed 1.5, 1.6, and 1.8 comparisons in [CI-RESULTS.md](CI-RESULTS.md)
locate the older compatibility boundaries; rerun those versions once during
final compatibility review rather than on every iteration.

The runner retains support for that older-version sweep. Packages requiring
installation metadata skip before 1.6; those requiring build-path removal skip
before 1.9. Other packages allow recorded build paths before 1.9, but still
require successful native execution. No test silently substitutes linker flags
for an unsupported `install_rpath` feature.

The one-time `rpath-packages.yml` workflow runs these comparisons on Linux,
macOS arm64, macOS Intel, and a Conda compiler environment. The three referenced
backend commits must be reachable in the GitHub repository before running it.
Push `rpath-fixes-astra` before pushing `rpath-regression-tests`.
Both workflows have a push trigger restricted to `rpath-regression-tests`, so
pushing that branch runs them without adding workflow files to the default
branch. A manual-dispatch trigger is also provided for repositories where the
workflow is registered. There is no scheduled or pull-request trigger.

## One-time downstream validation

`rpath-downstream.yml` runs the four pinned sources in `projects.json` against
the same three backend commits. Each OS/project job creates one Python
dependency constraint file and reuses it across all backends. The Pixi lock
pins native dependencies. Builds are serial within a comparison and continue
after failures, so one failing backend does not suppress the other results.

Run a project locally with the native dependencies installed:

```sh
python tools/rpath-validation/run.py dwave-optimization --backend /tmp/backend-astra --output /tmp/dwave-astra --lock /tmp/dwave-dependencies.lock
```

Use a fresh output directory for every invocation. `--repair` additionally
runs `auditwheel` or `delocate`, records a separate report, and hides the build
Python environment before testing the repaired wheel. Raw checks retain the
external dependency environment, hide the entire source/build checkout, and
remove loader overrides. Repair does not erase raw-wheel failures.

- **NumPy:** use the pinned `scipy-openblas64` wheel's `.pc` with an absolute
  library filename and RPATH. No runtime preloading is added. Matrix
  multiplication, a solve, and the NumPy linear-algebra test subset exercise
  native dependencies.
- **GridFire:** use the issue-era shared-library revision, not current static
  defaults. Populate its libplugin wrap redirect before Meson configuration.
  Dependency/bootstrap failures are retained separately from wheel inspection.
- **VapourSynth:** build the pinned upstream package and evaluate a native frame.
  Preserve its original macOS anchor behavior so failures remain visible.
- **D-Wave Optimization:** exercise nested extensions and native model
  evaluation with NumPy 2.0.0. BLAS and upstream C++ tests are disabled for this
  focused check. Its backend version bound is deliberately overridden.

The runner substitutes the selected backend for each project's backend
requirement and records that override. Other upstream requirements are retained.
It stores source/submodule/backend revisions, dependency versions, `.pc` output,
compiler information, wheel hashes, headers, and command logs. Source pins are
fixed; the first run resolves Python build requirements and writes the shared
lock before the backend comparisons continue.

Native macOS results and downstream workflows must be reported as pending until
executed. See `RESULTS.md` for the local Linux comparison results.

Before pushing the suite branch to start a comparison, publish the saved backend
branch (`git push origin rpath-fixes-astra`). Its commit is outside the suite's
history, so publishing the suite alone does not publish the saved implementation.
Both workflows pin complete backend commit IDs. See [RESULTS.md](RESULTS.md) for
the first run's setup failures and partial downstream results.

The [second CI analysis](CI-RESULTS.md) contains the complete package matrix,
confirmed downstream loader failures, and GridFire environment corrections.

GridFire uses Conda's zlib development files and explicit Boost directories. Its
Linux builds also receive `-pthread` because the pinned liblogging subproject
omits that dependency. These setup corrections apply equally to every backend.

## Long builds and interrupted jobs

The runner prints each command **before** starting it, streams stdout and stderr
live, and emits a heartbeat every 30 seconds. Full streams are also flushed to
`logs/NNN.stdout.log` and `logs/NNN.stderr.log`. Stdout remains separate from
stderr because pkg-config output and dependency locks must not contain diagnostics.

Each backend has a 25-minute budget (`--timeout 1500`). Ordinary commands,
including downloads and environment creation, have a five-minute limit
(`--command-timeout 300`); the wheel build has a 20-minute limit
(`--build-timeout 1200`). Every command is capped by the remaining backend budget.
On timeout, the runner sends SIGTERM to the whole process group, then SIGKILL
if needed, so Ninja's compilers cannot keep running or hold output pipes open.
A timeout is a failed comparison, and the workflow continues with the next
backend. The existing 90-minute job limit remains a final backstop.

`report.json` and `commands.json` are checkpointed before and after commands with
atomic replacement. A running command has a `running` state and log paths; a
completed timeout has `timed_out`, elapsed time, exit status, and captured output.
Cancellation records `interrupted` and retains the partial log files. CI uploads
these files and Meson's build logs even when comparison fails. On a hard runner
shutdown, the last checkpoint and any logs already written remain available for
artifact upload if the runner can still execute that step.

GridFire's diagnostic configuration now uses `-Doptimization=0`. The pinned
project propagates its core sources into many targets, making repeated optimized
compilation expensive. Disabling optimization reduces that work without patching
upstream source or changing its RPATH options, and applies equally to all three
backends. This comparison does not cover optimization-specific linker behavior.
Several dependencies unconditionally add their own tests; the top-level
`build-tests=false` cannot disable those without patching upstream.
Compilation parallelism remains two jobs by default; override with `--jobs` when
appropriate for the runner's memory and CPU limits.

The subprocess behavior has separate process-level tests (not RPATH unit tests):

```sh
python -m pytest tools/rpath-validation/test_commands.py -q
```

CI runs these on Linux and macOS before the downstream comparison. They check
live output, separate streams, exit statuses, heartbeats, a stubborn descendant
after its parent exits, backend budget expiry, and SIGTERM cancellation with
partial reports preserved.

Local validation: the five process tests passed; a real GridFire build with an
intentionally shortened 120-second build limit terminated at that deadline,
retained partial compiler output and JSON, and left no processes in its build
tree. A complete DWave/Astra run passed all 26 native-file checks and its installed
smoke test. This verifies timeout handling, not that GridFire's full build fits
the default 20-minute limit; that remains to be measured in CI.
