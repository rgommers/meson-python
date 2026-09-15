# Local RPATH comparison results

Executed on Linux aarch64 with Python 3.12 and the Conda compiler environment.
The input binaries normally carry DT_RPATH in this environment. Native macOS downstream smoke results are recorded below; package results and Windows execution remain unavailable.

Backend code: main `cbe2ac4`, PR rewrite `2a2a7ae`, saved implementation `5bda04e`.
The test branch has no production-code changes relative to the PR rewrite.

## Meson version matrix

| Meson | main | PR rewrite | Saved implementation |
| --- | --- | --- | --- |
| 1.5.0 | 5 failed, 5 passed, 12 skipped | 5 failed, 5 passed, 12 skipped | 10 passed, 12 skipped |
| 1.6.0 | 8 failed, 6 passed, 8 skipped | 11 failed, 3 passed, 8 skipped | 14 passed, 8 skipped |
| 1.8.0 | 8 failed, 6 passed, 8 skipped | 11 failed, 3 passed, 8 skipped | 14 passed, 8 skipped |
| 1.9.0 | 11 failed, 8 passed, 3 skipped | 15 failed, 4 passed, 3 skipped | 1 failed, 18 passed, 3 skipped |
| 1.11.1 | 11 failed, 8 passed, 3 skipped | 15 failed, 4 passed, 3 skipped | 1 failed, 18 passed, 3 skipped |

Meson 1.8.0 is a yanked release used here to check the original boundary; the workflow selects a patch release from the 1.8 series.
Skips cover unavailable introspection features and native macOS-only cases. Failures are normal assertions, not xfails.

## Per-package results with Meson 1.11.1

| Package | main | PR rewrite | Saved implementation |
| --- | --- | --- | --- |
| `rpath-build-only-removal` | FAIL: headers | FAIL: headers | PASS |
| `rpath-elf-install-precedence` | PASS | FAIL: headers / load | PASS |
| `rpath-elf-rpath-transitive` | FAIL: headers / load | FAIL: headers / load | PASS |
| `rpath-elf-runpath-direct` | FAIL: headers / load | PASS | PASS |
| `rpath-in-package-flat` | PASS | FAIL: headers | PASS |
| `rpath-in-package-nested` | FAIL: headers / load | FAIL: headers | PASS |
| `rpath-install-build-overlap` | PASS | FAIL: headers | PASS |
| `rpath-install-multiple` | FAIL: headers | FAIL: headers | PASS |
| `rpath-ldflags` | FAIL: headers | FAIL: headers | PASS |
| `rpath-legacy-origin-flat` | PASS | FAIL: headers | PASS |
| `rpath-link-args-relative` | FAIL: headers | FAIL: headers | PASS |
| `rpath-macos-duplicates-remove` | macOS only | macOS only | macOS only |
| `rpath-macos-duplicates-retain` | macOS only | macOS only | macOS only |
| `rpath-macos-path-spaces` | macOS only | macOS only | macOS only |
| `rpath-mixed-layout` | FAIL: headers / load | FAIL: headers | PASS |
| `rpath-no-dependencies` | PASS | PASS | PASS |
| `rpath-pkgconfig-absolute` | PASS | PASS | PASS |
| `rpath-pkgconfig-search` | PASS | PASS | PASS |
| `rpath-relocated-chain` | FAIL: headers | FAIL: headers | PASS |
| `rpath-relocated-multiple` | FAIL: headers | FAIL: headers | PASS |
| `rpath-relocated-single` | FAIL: headers | FAIL: headers | PASS |
| `sharedlib-in-package-orig` | PASS | FAIL: headers / load | FAIL: headers / load |

Main failures include both pre-existing defects and features introduced by the rewrite; a red main result alone does not establish a rewrite regression.

The unchanged original package passes on main. With Meson 1.9+, both the rewrite and the saved implementation remove its `$ORIGIN/sub` path, and loading `libexamplelib2.so` fails. This remains an explicit compatibility failure.

The saved implementation passes all 18 applicable new Linux packages with modern Meson. The rewrite fails the colon-list/idempotence, ELF precedence, and transitive-loading cases, and changes DT_RPATH to DT_RUNPATH in many otherwise working layouts.

Both pkg-config fixtures pass on all three backends in this environment. They are controls for the OpenBLAS-style absolute library filename/RPATH and conventional -L/-l forms.

## Downstream driver check

The new downstream runner was exercised against D-Wave Optimization at `0962fc5e3ac4adfec1d2b592ef7a0b3c016f39cd`, with backend `5bda04e`, NumPy 2.0.0, Meson 1.12.0, and BLAS disabled. All 26 native files passed raw-wheel checks; installed native model evaluation passed after hiding the source/build checkout.

Artifacts from this session are under `/tmp/rpath-reports/` and `/tmp/rpath-downstream-script-check2/`. The workflows upload equivalent reports and wheel artifacts.

## First CI runs: 15 September 2026

Both workflows ran suite commit `b63c19d75f21f30dec4aa42c9000f7fd9368b58f`,
before the runner readability refactor. Their overall red status mixes workflow
setup failures with downstream failures; it is not a package-test result.

### Package workflow: no tests executed

[Run 34934235034](https://github.com/rgommers/meson-python/actions/runs/34934235034)
had 48 failed jobs and no uploaded artifacts. In every job, the suite checkout
succeeded but the backend checkout failed. The checkout action interpreted the
seven-character commit IDs as branch/tag names, fetching patterns such as
`refs/heads/cbe2ac4*` instead of a commit. None reached dependencies or pytest.

The workflow now uses full 40-character IDs. Separately, the saved implementation
`5bda04efab456acc04673235ec09b376078f4b1c` was unavailable from the fork when checked
through the GitHub API. Its `rpath-fixes-astra` branch must be published before
rerunning; changing the SHA spelling alone cannot make that object available.

### Downstream workflow: partial comparison

[Run 34934235099](https://github.com/rgommers/meson-python/actions/runs/34934235099)
had eight failed jobs and eight uploaded artifacts. All jobs attempted main and
the PR rewrite, then stopped at `git worktree add` with
`fatal: invalid reference: 5bda04e`. There are no saved-implementation results.

The following outcomes come from the command exit statuses in the job logs.
“Smoke passed” does **not** assert that all header checks passed: the old driver
kept header errors and subprocess stderr in artifact JSON rather than printing
them. Artifact downloads from the storage endpoints timed out in this workspace,
so their detailed header results and failure tracebacks have not been inspected.

| Project | Linux main | Linux PR rewrite | macOS main | macOS PR rewrite |
| --- | --- | --- | --- | --- |
| NumPy + scipy-openblas64 | Build and smoke passed | Build and smoke passed | Build and smoke passed | Build and smoke passed |
| VapourSynth | Build and smoke passed | Build and smoke passed | Build and smoke passed | Built; smoke failed |
| DWave Optimization | Build and smoke passed | Build and smoke passed | Build and smoke passed | Built; smoke failed |
| GridFire | Build failed | Build failed | Build failed | Build failed |

NumPy's smoke command includes matrix multiplication, a linear solve, and its
fast linear-algebra tests. VapourSynth creates a frame through the native core;
DWave imports its native symbols and evaluates a small model.

The macOS VapourSynth and DWave results establish runtime regressions in these
comparisons, with the project revision and Python dependency constraints shared
between backends. The exact loader errors and offending LC_RPATH commands still
need the artifact reports; the command exit statuses alone do not establish their
cause. GridFire did not reach wheel auditing or installed execution, so these
runs cannot establish its RPATH behavior.

### Changes for the next run

- Use complete commit IDs in backend checkouts.
- Explicitly fetch each downstream backend before creating its worktree. Report
  an unavailable backend and continue the comparison instead of aborting the loop.
- Print the downstream report's errors to stderr as well as saving JSON. This
  includes build failure output and header problems. Failed smoke commands also
  print their captured output, so loader tracebacks are visible in the job log.
- Publish `rpath-fixes-astra` before rerunning the updated suite branch.

No repaired-wheel comparison or Windows execution was performed in these runs.
