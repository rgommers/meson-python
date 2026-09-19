# RPATH CI results

## Current checkpoint

This report describes the latest completed runs, replacing the older running
chronology. Historical details remain available in Git history.

- [Downstream run 35445578898](https://github.com/rgommers/meson-python/actions/runs/35445578898)
- [Package run 35445578975](https://github.com/rgommers/meson-python/actions/runs/35445578975)
- [Supplemental run 35445578909](https://github.com/rgommers/meson-python/actions/runs/35445578909)
- Suite commit: `2d397780cfe5e3c1edf5e6ee2467a733f3851630`

| Backend | Pinned commit |
| --- | --- |
| main | `cbe2ac407957ac0d8b0c5365a02d21dcade12822` |
| PR rewrite | `ddfcd049d0dfca8821195af396aa45afaa156948` |
| Astra | `722f285c396d4c38dedb198a2c6a6c23b85bf591` |

**The PR and Astra pass all six downstream combinations, including both header
checks and installed-wheel runtime tests.** The sole failing downstream job is
Linux DWave with main: it retains 23 literal linker-padding entries. All 18
backend/project/platform combinations build and run successfully.

The corrected `sharedlib-in-package-orig` now passes with the PR on system
Linux, including musl. On Conda its import succeeds but tag preservation still
fails. On macOS the second wheel build exposes the same no-edit command bug
as `rpath-mixed-layout`; this is no longer a missing-installation-path failure.
Astra passes every applicable Linux case; its only remaining package failure is
macOS duplicate retention when the wheel builder skips RPATH processing.

Routine macOS jobs now use `macos-latest` (macOS 26.6.2 ARM64 in these runs).
The supplemental jobs cover Alpine/musl x86_64 and macOS 15 Intel with Meson
1.12, running main only for packages that fail with the PR.

## Downstream results

A pass here requires a successful build, clean header checks under the corrected
harness policy, and the installed-wheel runtime check. These are raw wheels,
before auditwheel/delocate repair. Runtime testing hides the source/build
checkout and clears loader-path environment overrides.

| Project | Platform | main | PR rewrite | Astra |
| --- | --- | --- | --- | --- |
| NumPy + scipy-openblas64 | Ubuntu 24.04 | Pass | Pass | Pass |
| NumPy + scipy-openblas64 | macOS 26 ARM | Pass | Pass | Pass |
| VapourSynth | Ubuntu 24.04 | Pass | Pass | Pass |
| VapourSynth | macOS 26 ARM | Pass | Pass | Pass |
| dwave-optimization | Ubuntu 24.04 | 23 padding findings; runtime passes | Pass | Pass |
| dwave-optimization | macOS 26 ARM | Pass | Pass | Pass |

The runtime checks exercise NumPy linear algebra (including its linalg test
suite), VapourSynth frame creation, and a DWave model with native symbols and
objective evaluation. They are not exhaustive downstream test suites. Project
revisions and dependency requirements remain pinned in `projects.json`; each
job uses one dependency lock across its three backend builds.

### Why Linux DWave is still red

[Job 105903815333](https://github.com/rgommers/meson-python/actions/runs/35445578898/job/105903815333)
reports the following findings only for main (`cbe2ac4`):

- `_utilities.cpython-312-x86_64-linux-gnu.so` retains `XXXXXXX`.
- The 22 extension modules under `dwave/optimization/symbols/` each retain `XX`.

The diagnostic category is named `empty or padding RPATH`, but all 23 entries
in this run are actual nonempty strings of `X` characters. They are Meson's
linker padding left in the wheel, not false reports about `$ORIGIN`, not missing
libraries, and not runtime test failures. The PR and Astra remove them and have
zero header findings.

The workflow accumulates errors across all three backends. Main's known header
failures therefore make the job red even though the PR and Astra are clean.
The strict padding check is reporting real header content; no checker fix is
needed for this result. Removing every baseline defect is not a merge condition
for the PR. If a green comparison job becomes a requirement, baseline findings
would need a separate reporting policy rather than being silently suppressed.

### Harness corrections validated in this run

All six downstream jobs passed all **16 harness tests**. The missing parent of
`reports/harness-tests` is fixed. No checkout, setup, timeout, or preliminary
harness-test failure prevented a downstream comparison.

The previously reported retained-build-path findings are gone:

- macOS installation metadata using `$ORIGIN` is compared with its translated
  `@loader_path` spelling.
- A relative path listed in build metadata is not classified as build-only if
  it still reaches another native file in the installed wheel. This permits
  redundant but valid installed routes; it does not establish that each route
  is needed by an actual dependency.
- Duplicates, padding, literal macOS `$ORIGIN`, absolute source/build paths,
  and stale relative build paths remain checked independently.

This removes the false flags in macOS VapourSynth and DWave, and the relative
`$ORIGIN` findings in main/Astra Linux DWave. The surviving 23 padding findings
are a different category. The prior intermittent timeout-state failure did not
recur; additional diagnostics and retained partial reports are now available
if it does. This run alone does not establish its original cause.

## Small-package totals

All 15 routine jobs ran all 26 cases and uploaded their artifacts. Three Linux jobs
(Astra with two system-compiler Meson selections and Astra with Conda) passed;
the other jobs failed package expectations, not harness setup.

Cells are **passed / failed / skipped**. System-compiler Meson 1.9 and 1.12
results agree. The supplemental Intel PR outcomes agree with ARM. The Conda
job uses its resolved Meson version and a compiler configuration that emits DT_RPATH.

| Environment | main | PR rewrite | Astra |
| --- | --- | --- | --- |
| Linux x86_64, system compiler | 10/13/3 | 18/5/3 | 23/0/3 |
| Linux aarch64, Conda compiler | 9/14/3 | 6/17/3 | 23/0/3 |
| macOS 26 ARM | 8/11/7 | 14/5/7 | 18/1/7 |

## Supplemental platforms

Both jobs passed all five supplemental-runner tests, ran all 26 package cases,
and reran exactly the failing cases on main. No setup failure or timeout
prevented a comparison. Cells are **passed / failed / skipped**; baseline
counts cover only the selected failures, not the full suite.

| Environment | PR full suite | main, failing cases only |
| --- | --- | --- |
| Alpine/musl x86_64, Meson 1.12 | 18/5/3 | 1/4/0 |
| macOS 15 Intel, Meson 1.12 | 14/5/7 | 1/4/0 |

On musl, the five PR failures are build-only removal, installation-path
precedence, both mixed-tag chains, and transitive RPATH. Only precedence
passes on main. The three tag-conversion cases have successful runtime checks;
the transitive case also reports an empty entry in the middle library. Unlike
glibc, musl does not lose transitive lookup when RPATH becomes RUNPATH. The
header-preservation requirement still fails. Both dual-tag cases pass,
including the expected loader failure for deliberately empty RUNPATH.

On Intel macOS, the PR failures are duplicate removal, duplicate retention,
paths containing spaces, mixed layout, and the corrected original fixture.
Only the original fixture passes on main. The failure causes match ARM,
including the second-build no-edit invocation for the corrected fixture.

The jobs intentionally remain red when main also fails: a shared failing test
can have different causes in the two backends. These runs add no new class of
platform-specific defect, but confirm that the existing failures also occur
on the supplemental platforms.

## Per-package results

Each pass includes the package's header expectations, two wheel builds from
one build directory, and its installed smoke test. A failure may be a header
mismatch, build failure, or runtime failure; the interpretations below identify
which ones matter for review. `Skip` means the package is platform-specific.
The deliberately empty-RUNPATH case passes only when the expected loader
failure occurs.

### Linux, system compiler (Meson 1.9 and 1.12)

| Package | main | PR rewrite | Astra |
| --- | --- | --- | --- |
| `rpath-build-only-removal` | **Fail** | **Fail** | Pass |
| `rpath-elf-both-tags` | **Fail** | Pass | Pass |
| `rpath-elf-both-tags-empty-runpath` | Pass | Pass | Pass |
| `rpath-elf-install-precedence` | Pass | **Fail** | Pass |
| `rpath-elf-mixed-rpath-runpath` | **Fail** | **Fail** | Pass |
| `rpath-elf-mixed-runpath-rpath` | **Fail** | **Fail** | Pass |
| `rpath-elf-rpath-transitive` | **Fail** | **Fail** | Pass |
| `rpath-elf-runpath-direct` | **Fail** | Pass | Pass |
| `rpath-in-package-flat` | Pass | Pass | Pass |
| `rpath-in-package-nested` | **Fail** | Pass | Pass |
| `rpath-install-build-overlap` | Pass | Pass | Pass |
| `rpath-install-multiple` | **Fail** | Pass | Pass |
| `rpath-ldflags` | **Fail** | Pass | Pass |
| `rpath-legacy-origin-flat` | Pass | Pass | Pass |
| `rpath-link-args-relative` | **Fail** | Pass | Pass |
| `rpath-mixed-layout` | **Fail** | Pass | Pass |
| `rpath-no-dependencies` | Pass | Pass | Pass |
| `rpath-pkgconfig-absolute` | Pass | Pass | Pass |
| `rpath-pkgconfig-search` | Pass | Pass | Pass |
| `rpath-relocated-chain` | **Fail** | Pass | Pass |
| `rpath-relocated-multiple` | **Fail** | Pass | Pass |
| `rpath-relocated-single` | Pass | Pass | Pass |
| `sharedlib-in-package-orig` | Pass | Pass | Pass |

### Linux, Conda compiler

| Package | main | PR rewrite | Astra |
| --- | --- | --- | --- |
| `rpath-build-only-removal` | **Fail** | **Fail** | Pass |
| `rpath-elf-both-tags` | **Fail** | Pass | Pass |
| `rpath-elf-both-tags-empty-runpath` | Pass | Pass | Pass |
| `rpath-elf-install-precedence` | Pass | **Fail** | Pass |
| `rpath-elf-mixed-rpath-runpath` | **Fail** | **Fail** | Pass |
| `rpath-elf-mixed-runpath-rpath` | **Fail** | **Fail** | Pass |
| `rpath-elf-rpath-transitive` | **Fail** | **Fail** | Pass |
| `rpath-elf-runpath-direct` | **Fail** | Pass | Pass |
| `rpath-in-package-flat` | Pass | **Fail** | Pass |
| `rpath-in-package-nested` | **Fail** | **Fail** | Pass |
| `rpath-install-build-overlap` | Pass | **Fail** | Pass |
| `rpath-install-multiple` | **Fail** | **Fail** | Pass |
| `rpath-ldflags` | **Fail** | **Fail** | Pass |
| `rpath-legacy-origin-flat` | Pass | **Fail** | Pass |
| `rpath-link-args-relative` | **Fail** | **Fail** | Pass |
| `rpath-mixed-layout` | **Fail** | **Fail** | Pass |
| `rpath-no-dependencies` | Pass | Pass | Pass |
| `rpath-pkgconfig-absolute` | Pass | Pass | Pass |
| `rpath-pkgconfig-search` | Pass | Pass | Pass |
| `rpath-relocated-chain` | **Fail** | **Fail** | Pass |
| `rpath-relocated-multiple` | **Fail** | **Fail** | Pass |
| `rpath-relocated-single` | **Fail** | **Fail** | Pass |
| `sharedlib-in-package-orig` | Pass | **Fail** | Pass |

### macOS 26 ARM (Meson 1.9 and 1.12)

| Package | main | PR rewrite | Astra |
| --- | --- | --- | --- |
| `rpath-build-only-removal` | **Fail** | Pass | Pass |
| `rpath-in-package-flat` | Pass | Pass | Pass |
| `rpath-in-package-nested` | **Fail** | Pass | Pass |
| `rpath-install-build-overlap` | Pass | Pass | Pass |
| `rpath-install-multiple` | **Fail** | Pass | Pass |
| `rpath-ldflags` | **Fail** | Pass | Pass |
| `rpath-legacy-origin-flat` | Pass | Pass | Pass |
| `rpath-link-args-relative` | **Fail** | Pass | Pass |
| `rpath-macos-duplicates-remove` | **Fail** | **Fail** | Pass |
| `rpath-macos-duplicates-retain` | **Fail** | **Fail** | **Fail** |
| `rpath-macos-path-spaces` | **Fail** | **Fail** | Pass |
| `rpath-mixed-layout` | **Fail** | **Fail** | Pass |
| `rpath-no-dependencies` | Pass | Pass | Pass |
| `rpath-pkgconfig-absolute` | Pass | Pass | Pass |
| `rpath-pkgconfig-search` | Pass | Pass | Pass |
| `rpath-relocated-chain` | **Fail** | Pass | Pass |
| `rpath-relocated-multiple` | **Fail** | Pass | Pass |
| `rpath-relocated-single` | Pass | Pass | Pass |
| `sharedlib-in-package-orig` | Pass | **Fail** | Pass |

All three macOS-specific packages skip on Linux. The seven ELF-specific
packages skip on macOS. Those skips are included in the totals above.

## Findings relevant to the PR

### ELF tag preservation

The PR still uses `patchelf --set-rpath` without preserving an existing
DT_RPATH-only tag. The mixed-tag chain packages expose the conversion on Linux;
the Conda compiler makes it visible in many otherwise successful layouts.
For example, `rpath-legacy-origin-flat`, `rpath-in-package-flat`, and
`rpath-install-build-overlap` have only tag-type failures in the Conda job,
not installed import failures.

On glibc, the transitive-RPATH package fails to load its leaf library with the
PR. The unmodified exploratory package also fails on main for a different reason, so
its two failures alone do not prove a regression. Separately, a local variant
with an explicit link-time `$ORIGIN/lib` path already working on main produced:
main runs; PR cannot find the leaf; restoring only the original tag types in
the PR wheel makes it run. That is the focused runtime regression to capture
in a clean test package.

Preserve RPATH-only inputs without converting RUNPATH inputs or activating the
ignored RPATH of a dual-tag binary. Both dual-tag packages already pass with
the PR and Astra and should remain guardrails.

### ELF installation-path precedence

`rpath-elf-install-precedence` passes on main but fails on the PR with both
system and Conda compilers. Removing and re-appending the private installation
path places it after the preserved external path. The installed executable
loads the wrong same-SONAME library and fails its result check.

This is a runtime regression, not merely a preferred header ordering. Put
explicit installation paths before preserved paths in the resulting list.

### macOS command construction and path parsing

The following failures repeat on ARM with both Meson selections and on Intel
with Meson 1.12:

| Package | PR failure | Focused correction |
| --- | --- | --- |
| `rpath-mixed-layout`, `sharedlib-in-package-orig` | Second wheel build invokes `install_name_tool` with only the binary filename, because an ordering difference produces no actual edit arguments. | Skip the command when there are no edits. |
| `rpath-macos-path-spaces` | The parser truncates paths at whitespace; a second build tries to add an existing path and Apple tools reject it. | Preserve the full path before the final otool offset annotation, including meaningful whitespace. |
| `rpath-macos-duplicates-remove` | Identical `-delete_rpath` arguments occur twice in one invocation and Apple tools reject them. | Deduplicate deletion requests and verify all copies are removed. |

`rpath-mixed-layout` and the two macOS-specific editing cases also fail some main expectations. The corrected
`sharedlib-in-package-orig`, however, passes on main and fails on the PR:
it is now a valid regression reproducer for the no-edit command defect.
These identify three implementation fixes, not four separate causes. Astra
passes all four packages.

### Compatibility requirement and the original fixture

The single-library `rpath-legacy-origin-flat` package passes on macOS ARM/Intel
and system Linux. On Conda Linux it imports successfully but reports the tag
conversion above. VapourSynth and DWave now also pass on macOS with the PR.
This validates the anchor-translation compatibility fix for correct explicit
installation paths.

This run includes the fixture correction to request
`install_rpath: '$ORIGIN:$ORIGIN/sub'`, preserving its original layout and
legacy anchors while supplying the previously missing installation path.

| Environment | Corrected fixture with PR |
| --- | --- |
| System Linux/glibc, Meson 1.9 and 1.12 | Pass |
| Alpine/musl, Meson 1.12 | Pass |
| Conda Linux | Installed import and calculations pass; only RPATH-to-RUNPATH conversion fails |
| macOS ARM and Intel | Second wheel build fails: `install_name_tool` receives only the binary filename |

The macOS failure occurs during the second wheel construction, after
`meson setup --reconfigure` succeeds. It does not establish an import
failure for the corrected first wheel: the suite stops before the final smoke
test when the second build fails. It demonstrates the already identified
no-edit command bug with a valid installation configuration. Main and Astra
pass this corrected fixture in every environment where they were run.

Astra's broader layout-preservation shim remains useful for its compatibility
policy, but need not be added to the PR to address these results. The focused
PR corrections are still tag preservation, installation-path precedence, and
the three macOS editing fixes.

## Deferred findings and limitations

- `rpath-macos-duplicates-retain` is Astra's only remaining package failure.
  All three backends leave the two commands in place because the wheel builder
  skips RPATH processing when there are no relocation or path-metadata edits.
  General cleanup of otherwise untouched binaries is deferred.
- On system Linux, `rpath-build-only-removal` exposes the PR leaving an empty
  RUNPATH after removing all paths. Comprehensive empty-tag/padding handling
  is separate from the focused merge requirements. Deliberately empty RUNPATH
  in a dual-tag binary must remain distinguishable from this case.
- GridFire remains disabled: the earlier Linux builds exceeded their budgets,
  and macOS builds exposed a separate fourdst import issue. No current GridFire
  success is claimed; revisit at final validation or ask its author to test.
- The package tests describe more desired behavior than this PR must deliver.
  Their overall red status is not itself grounds for blocking the PR. The
  agreed focused work is ELF tag preservation and precedence, plus the three
  macOS editing fixes above.
- No repaired-wheel run is included. Musl validation covers the small packages,
  not downstream projects. Intel now runs only the PR and selective main
  comparisons with Meson 1.12; Astra and Meson 1.9 Intel results are not part of
  this checkpoint. Coverage does not extend to every downstream build option.

## Evidence and reproducibility

This update was checked against job logs and per-test outcomes in all three
runs, including all three backend sections of every downstream job and both
supplemental baseline reruns. All routine jobs uploaded package artifacts.
Local copies of the logs are under `/tmp/rpath-ci-review/35445578898/`,
`/tmp/rpath-ci-review/35445578975/`, and `/tmp/rpath-ci-review/35445578909/`;
these temporary files are not required to read the linked CI evidence.

Compared with the previous checkpoint, the suite adds supplemental platforms,
uses current ARM macOS for routine jobs, and corrects the original fixture's
installation paths. Backend pins and checker policy are unchanged. The fixture
correction removes the missing-subdirectory failure; it does not remove the
independent tag-conversion and macOS repeated-build defects.
