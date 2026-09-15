# rpath-elf-mixed-runpath-rpath

Preserve an executable with DT_RUNPATH and a middle library with DT_RPATH.

## Layout and inputs

The build has `probe-exe` → `middle/libmiddle.so` → `leaf/libleaf.so`.
Per-target linker flags explicitly select the two different tags; the runner
asserts the input tag types before wheel generation. Neither the system linker
nor the Conda toolchain is allowed to determine these types implicitly.

The wheel separates the middle and leaf libraries into different directories.
The leaf moves from build directory `leaf/` to `probe/installed-leaf/`, forcing
a path edit in the middle library even without compiler-injected paths.
The executable's search path cannot find the leaf; the middle library must
supply its own path. This exercises mixed tags across a dependency chain,
complementing the single-tag transitive and direct-dependency packages.

## Expected wheel headers and execution

| Installed binary | Linux expectations | macOS LC_RPATH |
| --- | --- | --- |
| `probe/probe-exe` | DT_RUNPATH: `$ORIGIN/middle` | Not applicable |
| `probe/middle/libmiddle.so` | DT_RPATH: `$ORIGIN/../installed-leaf` | Not applicable |
| `probe/installed-leaf/libleaf.so` | No project paths | Not applicable |

Each project path occurs exactly once. Build paths and padding must disappear;
compiler-injected paths measured by the dependency-free control remain allowed
and must be preserved. Neither explicit tag may be converted into the other.
The second wheel build must preserve the first wheel's paths and tag types.
After the source and build directories are removed, the installed executable
must return success: `middle()` calls `leaf()`, which returns 42.

This is a Linux-only package requiring Meson >= 1.9. macOS skips it.

Run from the meson-python checkout:

```sh
python -m pytest tests/test_rpath_packages.py -k 'rpath_elf_mixed_runpath_rpath' -vv
```

For a manual build, run `python -m build --wheel --no-isolation -Cbuild-dir=build`
in this directory. Install into a fresh environment, hide the source and build
directories, then run `smoke.py` outside them with `LD_LIBRARY_PATH` unset.
