# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

import pathlib
import subprocess
import sys


prefix = pathlib.Path(sys.argv[1]).resolve()
build = prefix.parent / 'provider-build'
source = pathlib.Path(__file__).parent / 'provider'
subprocess.run(['meson', 'setup', str(build), str(source), '--prefix=' + str(prefix), '--libdir=lib'], check=True)
subprocess.run(['meson', 'install', '-C', str(build)], check=True)
lib = next(path for path in (prefix / 'lib').glob('libexternal.*') if path.suffix in {'.so', '.dylib'})
flags = str(lib)
pc = prefix / 'lib/pkgconfig/external.pc'
pc.parent.mkdir(parents=True, exist_ok=True)
pc.write_text(f'''prefix={prefix}
libdir=${{prefix}}/lib
Name: external
Description: Standalone provider for the RPATH regression package
Version: 1.0
Libs: {flags} -Wl,-rpath,${{libdir}}
''')
