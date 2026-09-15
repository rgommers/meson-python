# rpath-macos-duplicates-retain

Deduplicate an existing LC_RPATH while retaining its path.

## Layout and inputs

Build: _probe has two LC_RPATH commands for @loader_path/dupa.

Wheel: probe/_probe retains exactly one @loader_path/dupa.

Run this package alone from the meson-python checkout:

```sh
python -m pytest tests/test_rpath_packages.py -k 'rpath_macos_duplicates_retain' -vv
```

For a manual build, run `python -m build --wheel --no-isolation -Cbuild-dir=build` in this directory.
Install the resulting wheel into a fresh environment, hide `build`, then run `smoke.py` outside the source directory.

## Expected wheel headers

Platforms: darwin. Meson >= 1.9.

| Installed binary | Linux path entries | macOS LC_RPATH entries |
| --- | --- | --- |
| `probe/_probe*` | Not applicable | `@loader_path/dupa` |

Each listed path must occur exactly once. No unlisted project paths or ELF padding entries may remain.
Compiler-injected paths measured in the dependency-free control are allowed and must be preserved.
Before Meson 1.9, additional build paths reported by the input metadata are allowed; runtime success is still required.
ELF retains the input dynamic tag when a path remains; empty results remove the tag. macOS checks counts without requiring reordered retained entries.
Where `ordered` is true in `expectations.json`, the listed ELF entries must appear in that order.

A second wheel build must leave paths and counts unchanged. Every smoke test requires success; known backend bugs are ordinary failures.

The machine-readable assertions are in `expectations.json`; the runner captures original headers and installation metadata for comparison.

## Prepared input

A Meson custom target replaces one equal-length seed load-command path after linking.
The input must contain two `@loader_path/dupa` commands before wheel processing.
This tests real Apple tools against real native files, without mocking or invoking meson-python RPATH helpers.
