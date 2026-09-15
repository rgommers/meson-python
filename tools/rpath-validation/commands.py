# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Stream commands to CI and disk, and bound the lifetime of their process trees."""

import os
import selectors
import signal
import subprocess
import sys
import time


def stream_command(command, cwd, env, log_prefix, timeout, heartbeat=30, kill_grace=5):
    """Return (CompletedProcess, timed_out), preserving stdout separately from stderr.

    Separate streams matter: callers use stdout as pkg-config data and pip locks.
    Process groups also cover Ninja's compilers and children holding output pipes
    open after their parent exits. This runner targets Linux and macOS.
    """
    started = time.monotonic()
    deadline = started + timeout
    next_heartbeat = started + heartbeat
    kill_at = float('inf')
    timed_out = False
    stdout, stderr = [], []
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)

    def kill_group(sig):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    try:
        with selectors.DefaultSelector() as selector, \
                log_prefix.with_suffix('.stdout.log').open('wb') as stdout_log, \
                log_prefix.with_suffix('.stderr.log').open('wb') as stderr_log:
            selector.register(process.stdout, selectors.EVENT_READ, (stdout, stdout_log, sys.stdout))
            selector.register(process.stderr, selectors.EVENT_READ, (stderr, stderr_log, sys.stderr))
            while selector.get_map() or process.poll() is None:
                now = time.monotonic()
                if not timed_out and now >= deadline:
                    timed_out = True
                    print(f'Command timed out after {timeout:.1f}s; terminating its process group.', flush=True)
                    kill_group(signal.SIGTERM)
                    kill_at = now + kill_grace
                if now >= kill_at:
                    kill_group(signal.SIGKILL)
                    kill_at = float('inf')
                if now >= next_heartbeat:
                    print(f'Command still running ({now - started:.0f}s elapsed). Logs: {log_prefix}.*.log', flush=True)
                    next_heartbeat = now + heartbeat
                for key, _ in selector.select(timeout=0.1):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    chunks, log, console = key.data
                    chunks.append(chunk)
                    log.write(chunk)
                    log.flush()
                    print(chunk.decode(errors='replace'), end='', file=console, flush=True)
    finally:
        # Also clean up descendants on cancellation or an output/logging error.
        kill_group(signal.SIGKILL)
        process.wait()
        process.stdout.close()
        process.stderr.close()
    result = subprocess.CompletedProcess(command, process.returncode,
                                         b''.join(stdout).decode(errors='replace'),
                                         b''.join(stderr).decode(errors='replace'))
    return result, timed_out
