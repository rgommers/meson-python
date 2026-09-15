# rpath-mixed-layout

Preserve an in-package private path alongside a single relocated-library path.

## Layout and inputs

Build: module.c → first/libfirst + second/libsecond + private/libprivate.

Wheel: probe/_probe → two relocated libraries + probe/private/libprivate.

Run this package alone from the meson-python checkout:

```sh
python -m pytest tests/test_rpath_packages.py -k 'rpath_mixed_layout' -vv
```

For a manual build, run `python -m build --wheel --no-isolation -Cbuild-dir=build` in this directory.
Install the resulting wheel into a fresh environment, hide `build`, then run `smoke.py` outside the source directory.

## Expected wheel headers

Platforms: linux, darwin. Meson >= 1.6.

| Installed binary | Linux path entries | macOS LC_RPATH entries |
| --- | --- | --- |
| `probe/_probe*` | `$ORIGIN/private`, `$ORIGIN/../.rpath_mixed_layout.mesonpy.libs` | `@loader_path/private`, `@loader_path/../.rpath_mixed_layout.mesonpy.libs` |
| `**/*second*` | No project paths | No project paths |
| `**/*first*` | No project paths | No project paths |
| `**/*private*` | No project paths | No project paths |

Each listed path must occur exactly once. No unlisted project paths or ELF padding entries may remain.
Compiler-injected paths measured in the dependency-free control are allowed and must be preserved.
Before Meson 1.9, additional build paths reported by the input metadata are allowed; runtime success is still required.
ELF retains the input dynamic tag when a path remains; empty results remove the tag. macOS checks counts without requiring reordered retained entries.
Where `ordered` is true in `expectations.json`, the listed ELF entries must appear in that order.

A second wheel build must leave paths and counts unchanged. Every smoke test requires success; known backend bugs are ordinary failures.

The machine-readable assertions are in `expectations.json`; the runner captures original headers and installation metadata for comparison.
