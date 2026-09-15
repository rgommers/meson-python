# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

project('rpath-mixed-layout', 'c', version: '1.0.0')

py = import('python').find_installation(pure: false)
origin = host_machine.system() == 'darwin' and get_option('anchor') == 'auto' ? '@loader_path' : '$ORIGIN'

# Two distinct build paths must collapse to a single mesonpy.libs path.
subdir('second')
subdir('first')
# This dependency stays inside the package, at a different relative path
# from its build location. Its installation RPATH must also survive.
subdir('private')
subdir('extension')
