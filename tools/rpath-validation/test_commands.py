# SPDX-FileCopyrightText: 2026 The meson-python developers
#
# SPDX-License-Identifier: MIT

"""Process-level checks for CI logging and cleanup, independent of RPATH rewriting."""

import json
import os
import pathlib
import signal
import subprocess
import sys
import time

from concurrent.futures import ThreadPoolExecutor

import pytest

from commands import stream_command


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail('Timed out waiting for subprocess progress')


def test_separate_streams_and_exit_status(tmp_path, capsys):
    code = 'import sys; print("stdout π"); print("stderr", file=sys.stderr); sys.exit(7)'
    result, timed_out = stream_command([sys.executable, '-c', code], tmp_path, os.environ,
                                      tmp_path / 'command', timeout=5)
    assert result.returncode == 7
    assert not timed_out
    assert result.stdout == 'stdout π\n'
    assert result.stderr == 'stderr\n'
    assert (tmp_path / 'command.stdout.log').read_text() == result.stdout
    assert (tmp_path / 'command.stderr.log').read_text() == result.stderr
    captured = capsys.readouterr()
    assert captured.out == result.stdout
    assert captured.err == result.stderr


def test_output_is_live_before_command_exits(tmp_path, capsys):
    release = tmp_path / 'release'
    code = ('import pathlib, time; print("started", flush=True)\n'
            f'while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.02)')
    with ThreadPoolExecutor() as pool:
        future = pool.submit(stream_command, [sys.executable, '-c', code], tmp_path, os.environ,
                             tmp_path / 'live', 5, 0.1)
        try:
            log = tmp_path / 'live.stdout.log'
            wait_for(lambda: log.exists() and 'started' in log.read_text())
            assert not future.done()
            assert 'started' in capsys.readouterr().out
            time.sleep(0.2)
            assert 'still running' in capsys.readouterr().out
        finally:
            release.touch()
        result, timed_out = future.result(timeout=5)
    assert result.returncode == 0
    assert not timed_out


def test_timeout_kills_child_after_parent_exits(tmp_path):
    # A descendant ignores SIGTERM and inherits the output pipes. Waiting only
    # for the original process would miss it, and joining pipe readers would hang.
    ready = tmp_path / 'ready'
    child = ('import pathlib, signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
             f'pathlib.Path({str(ready)!r}).touch(); print("child", flush=True); time.sleep(60)')
    parent = ('import pathlib, subprocess, sys, time\n'
              f'subprocess.Popen([sys.executable, "-c", {child!r}])\n'
              f'while not pathlib.Path({str(ready)!r}).exists(): time.sleep(0.01)')
    started = time.monotonic()
    result, timed_out = stream_command([sys.executable, '-c', parent], tmp_path, os.environ,
                                      tmp_path / 'tree', timeout=1, kill_grace=0.1)
    assert timed_out
    assert result.returncode == 0  # Parent exited; its child was the hung process.
    assert result.stdout == 'child\n'
    assert time.monotonic() - started < 5


@pytest.mark.parametrize('cancel', [False, True], ids=['deadline', 'sigterm'])
def test_runner_saves_partial_report(tmp_path, cancel):
    # Stop at the first checkout command; no network, compiler, or backend needed.
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    git = bin_dir / 'git'
    git.write_text('#!/bin/sh\necho partial-output\necho partial-error >&2\nsleep 60\n')
    git.chmod(0o755)
    output = tmp_path / 'report'
    env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
    command = [sys.executable, str(pathlib.Path(__file__).with_name('run.py')), 'gridfire',
               '--backend', str(tmp_path), '--output', str(output),
               '--timeout', '30' if cancel else '1', '--command-timeout', '30']
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        log = output / 'logs/000.stdout.log'
        wait_for(lambda: log.exists() and 'partial-output' in log.read_text())
        if cancel:
            running = json.loads((output / 'report.json').read_text())
            assert running['commands'][0]['state'] == 'running'
            process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=10)
    assert process.returncode == 1
    assert 'partial-output' in stdout
    assert 'partial-error' in stderr
    report = json.loads((output / 'report.json').read_text())
    assert report['errors']
    record = report['commands'][0]
    assert record['state'] == ('interrupted' if cancel else 'timed_out')
    assert record['timeout_seconds'] <= (30 if cancel else 1)
    assert (output / record['stderr_log']).read_text() == 'partial-error\n'
    assert json.loads((output / 'commands.json').read_text()) == report['commands']
