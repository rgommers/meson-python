# rpath-ldflags

Preserve intentional relative and absolute LDFLAGS paths during relocation.

## Layout and inputs

Build: module.c → first/libfirst; LDFLAGS apply to both targets.

Wheel: probe/_probe → relocated libfirst; preserve both flags on both binaries.

Run this package alone from the meson-python checkout:

```sh
python -m pytest tests/test_rpath_packages.py -k 'rpath_ldflags' -vv
```

For a manual build, run `python -m build --wheel --no-isolation -Cbuild-dir=build` in this directory.
Install the resulting wheel into a fresh environment, hide `build`, then run `smoke.py` outside the source directory.

## Expected wheel headers

Platforms: linux, darwin. Meson >= 0.64.

| Installed binary | Linux path entries | macOS LC_RPATH entries |
| --- | --- | --- |
| `probe/_probe*` | `$ORIGIN/user`, `<absolute external prefix>`, `$ORIGIN/../.rpath_ldflags.mesonpy.libs` | `@loader_path/user`, `<absolute external prefix>`, `@loader_path/../.rpath_ldflags.mesonpy.libs` |
| `**/*first*` | `$ORIGIN/user`, `<absolute external prefix>`, `$ORIGIN/.` | `@loader_path/user`, `<absolute external prefix>`, `@loader_path/.` |

Each listed path must occur exactly once. No unlisted project paths or ELF padding entries may remain.
Compiler-injected paths measured in the dependency-free control are allowed and must be preserved.
Before Meson 1.9, additional build paths reported by the input metadata are allowed; runtime success is still required.
ELF retains the input dynamic tag when a path remains; empty results remove the tag. macOS checks counts without requiring reordered retained entries.
Where `ordered` is true in `expectations.json`, the listed ELF entries must appear in that order.

A second wheel build must leave paths and counts unchanged. Every smoke test requires success; known backend bugs are ordinary failures.

The machine-readable assertions are in `expectations.json`; the runner captures original headers and installation metadata for comparison.

## Environment input

The runner supplies both an origin-relative `user` directory and an absolute external prefix through `LDFLAGS`.
For a manual build, supply those two RPATH flags explicitly, using the platform anchor.

Standalone Linux build with the same two flag forms:

```sh
LDFLAGS='-Wl,-rpath,$ORIGIN/user -Wl,-rpath,/tmp/rpath-external' python -m build --wheel --no-isolation -Cbuild-dir=build
```

On macOS, use `@loader_path/user` instead of `$ORIGIN/user`.
