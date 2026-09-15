# rpath-elf-both-tags

DT_RUNPATH must suppress DT_RPATH when both tags are present.

## Layout and inputs

The executable links the library in `good/`. The wheel installs it under
`probe/runpath-choice/`, and a distinguishable same-SONAME library from `bad/`
under `probe/rpath-choice/`. Both are named `librpath_test_choice.so`.

GNU linker flags normally select one tag type. `prepare_binary.py` constructs
a real dual-tag ELF input by splitting a reserved dynamic string and replacing
the executable's DT_DEBUG entry with DT_RPATH. It supports the little-endian
ELF64 targets used in CI (x86_64 and aarch64); it asserts the format and original
tags. No backend helper or patchelf operation creates the input. The build step
only edits freshly linked seed strings, so repeated wheel builds cannot restore
the original input and conceal an idempotency bug.

The runner asserts both input tags and their individual paths before building
the first wheel. DT_RPATH contains `$ORIGIN/rpath-choice`.
DT_RUNPATH contains `$ORIGIN/runpath-choice` and the build-only `$ORIGIN/good`; wheel processing must remove the latter.
Compiler-added paths are deliberately replaced in this prepared executable;
ordinary preservation checks still apply to the libraries.

## Expected wheel headers and execution

| Installed binary | Linux expectations | macOS LC_RPATH |
| --- | --- | --- |
| `probe/probe-exe` | `$ORIGIN/runpath-choice` in DT_RUNPATH; DT_RPATH may retain only `$ORIGIN/rpath-choice`, or be removed | Not applicable |
| `probe/runpath-choice/librpath_test_choice.so` | No project paths | Not applicable |
| `probe/rpath-choice/librpath_test_choice.so` | No project paths | Not applicable |

The inactive RPATH may be removed because it has no loader effect. It must never
be merged into RUNPATH. Assertions associate paths with each tag and distinguish
an empty RUNPATH from an absent tag; they do not compare a flattened union.
All checks apply to both wheel builds, whose headers must remain identical.

The executable must select the RUNPATH library, whose `choice()` returns 42.
The same-SONAME RPATH library returns 7, so merging or preferring RPATH makes
the executable fail.

These expectations follow the [glibc loader rules](https://man7.org/linux/man-pages/man8/ld.so.8.html):
DT_RPATH is considered only when DT_RUNPATH is absent. The fixtures target Linux
with glibc and Meson >= 1.9. macOS skips them.

Run from the meson-python checkout:

```sh
python -m pytest tests/test_rpath_packages.py -k 'rpath_elf_both_tags' -vv
```

For a manual build, run `python -m build --wheel --no-isolation -Cbuild-dir=build`
in this directory. Install the wheel into a fresh environment, hide the source
and build directories, and run `smoke.py` from an otherwise empty directory with
`LD_LIBRARY_PATH` unset. This also prevents an empty RUNPATH from finding a
library in the current directory.
