#!/usr/bin/env python3
"""Run pinned upstream J713 synthetic host tests; no private DTBs or hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import bringup

GROUPS = ['test_j713_runtime_import', 'test_j713_peripheral_calibration',
          'test_j713_optional_multifunction_calibration', 'test_j713_fdt_padding_guard']
WORKER = '''
import importlib.util, pathlib, sys
root, output = map(pathlib.Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location('pinned_j713', root / 'test/py/tests/test_apple_j713_fdt.py')
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)
groups = %r
for name in groups:
    if name == 'test_j713_fdt_padding_guard':
        getattr(suite, name)()
    else:
        directory = output / name
        directory.mkdir()
        getattr(suite, name)(directory)
    print('PASS ' + name, flush=True)
''' % GROUPS


def source_path(root, relative):
    if (relative.startswith('/') or '\\' in relative or
            any(x in ('', '.', '..') for x in relative.split('/'))):
        raise ValueError('Unsafe source path')
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Source path escapes cache')
    return path


def verify_sources(root, lock):
    for relative, expected in lock['files'].items():
        path = source_path(root, relative)
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or linked source: ' + relative)
        if path.stat().st_size > 1024 * 1024 or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Changed source bytes: ' + relative)


def fetch_sources(root, lock):
    for relative, expected in lock['files'].items():
        path = source_path(root, relative)
        if path.exists():
            continue  # Existing bytes are verified, never silently replaced.
        url = 'https://raw.githubusercontent.com/aurora-silicon/u-boot/' + lock['commit'] + '/' + relative
        with urllib.request.urlopen(url, timeout=60) as stream:
            content = stream.read(1024 * 1024 + 1)
        if len(content) > 1024 * 1024 or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError('Download differs from locked bytes: ' + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as output:
            output.write(content)


def run(fetch):
    lock = json.loads((bringup.ROOT / 'configs/j713-fixtures.lock.json').read_text())
    pins = json.loads((bringup.ROOT / 'configs/candidate-stack.json').read_text())
    if (lock['repository'] != 'aurora-silicon/u-boot' or lock['commit'] != pins['uboot_commit'] or
            not re.fullmatch('[0-9a-f]{40}', lock['commit'])):
        raise ValueError('Fixture revision must match the candidate U-Boot pin')
    for tool in ['cc', 'dtc']:
        if not shutil.which(tool):
            raise ValueError('Missing host build tool: ' + tool)
    root = bringup.WORK / 'j713-fixtures/sources'
    root.mkdir(parents=True, exist_ok=True)
    if fetch:
        fetch_sources(root, lock)
    verify_sources(root, lock)  # All source checks complete before importing upstream Python/C.
    bringup.REPORTS.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='j713-fixtures-', dir=bringup.REPORTS))
    environment = dict(os.environ)
    # Private hardware capture testing is deliberately not called, even if configured outside this runner.
    for key in ['APPLE_J713_RUNTIME_DTB', 'APPLE_J713_OS_DTBS', 'PYTHONPATH', 'PYTHONHOME']:
        environment.pop(key, None)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    timed_out = False
    with (attempt / 'host-tests.log').open('w') as log:
        process = subprocess.Popen([sys.executable, '-I', '-c', WORKER, str(root), str(attempt)],
                                   stdout=log, stderr=subprocess.STDOUT, env=environment, start_new_session=True)
        try:
            code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            code = process.returncode
    status = 'SYNTHETIC_IMPORTER_TIMEOUT' if timed_out else (
        'SYNTHETIC_IMPORTER_PASS' if code == 0 else 'SYNTHETIC_IMPORTER_FAILED')
    report = {'status': status,
              'uboot_commit': lock['commit'], 'source_sha256': lock['files'],
              'test_groups': GROUPS, 'synthetic_import_invocations': 56 if status == 'SYNTHETIC_IMPORTER_PASS' else None,
              'padding_compile_checks': 5 if status == 'SYNTHETIC_IMPORTER_PASS' else None,
              'host_compiler': bringup.capture(['cc', '--version']).splitlines()[0],
              'dtc_version': bringup.capture(['dtc', '--version']), 'exit_status': code,
              'native_boot_proven': False, 'private_captures_used': False,
              'hardware_helpers_executed': False,
              'note': 'Production importer/libfdt on the host with synthetic DTBs only. No firmware or hardware admission proof.'}
    bringup.save(attempt / 'result.json', report)
    print(json.dumps(report, indent=2))
    print('Logs and report: ' + str(attempt))
    if code or timed_out:
        print('\n'.join((attempt / 'host-tests.log').read_text(errors='replace').splitlines()[-30:]))
    return int(code != 0 or timed_out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', help='Fetch only missing locked sources; default is offline')
    args = parser.parse_args()
    try:
        return run(args.fetch)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
