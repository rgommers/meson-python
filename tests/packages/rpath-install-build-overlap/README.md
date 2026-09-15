# rpath-install-build-overlap

An explicit install path wins over removal of the same build path.

## Layout and inputs

Build: _probe with build_rpath=install_rpath.

Wheel: _probe keeps the explicitly installed `keep` path.

Run this package alone from the meson-python checkout:

```sh
python -m pytest tests/test_rpath_packages.py -k 'rpath_install_build_overlap' -vv
```

For a manual build, run `python -m build --wheel --no-isolation -Cbuild-dir=build` in this directory.
Install the resulting wheel into a fresh environment, hide `build`, then run `smoke.py` outside the source directory.

## Expected wheel headers

Platforms: linux, darwin. Meson >= 1.9.

| Installed binary | Linux path entries | macOS LC_RPATH entries |
| --- | --- | --- |
| `probe/_probe*` | `$ORIGIN/keep` | `@loader_path/keep` |

Each listed path must occur exactly once. No unlisted project paths or ELF padding entries may remain.
Compiler-injected paths measured in the dependency-free control are allowed and must be preserved.
Before Meson 1.9, additional build paths reported by the input metadata are allowed; runtime success is still required.
ELF retains the input dynamic tag when a path remains; empty results remove the tag. macOS checks counts without requiring reordered retained entries.
Where `ordered` is true in `expectations.json`, the listed ELF entries must appear in that order.

A second wheel build must leave paths and counts unchanged. Every smoke test requires success; known backend bugs are ordinary failures.

The machine-readable assertions are in `expectations.json`; the runner captures original headers and installation metadata for comparison.
