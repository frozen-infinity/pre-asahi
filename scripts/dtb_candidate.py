#!/usr/bin/env python3
"""Compile pinned j713 DT descriptions on the host. Never installs or boots them."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import urllib.request
import bringup

PROFILES = bringup.ROOT / 'configs/dtb-candidates.json'


def source_path(current, target, angled):
    if (PurePosixPath(current).is_absolute() or '..' in PurePosixPath(current).parts or
            '\\' in current or '\0' in current or
            target.startswith('/') or '\\' in target or '\0' in target):
        raise ValueError('Invalid include path')
    parts = ['include'] if angled else list(PurePosixPath(current).parent.parts)
    for part in target.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if not parts:
                raise ValueError('Include escapes source root')
            parts.pop()
        else:
            parts.append(part)
    path = '/'.join(parts)
    if (not (path.startswith('include/') or path.startswith('arch/arm64/boot/dts/apple/')) or
            PurePosixPath(path).suffix not in ('.dts', '.dtsi', '.h')):
        raise ValueError('Include outside the reviewed source areas: ' + path)
    return path


def includes(path, content):
    clean = re.sub(r'/\*.*?\*/', '', content, flags=re.S)
    found = []
    for line in clean.splitlines():
        if not re.match(r'^\s*#\s*include\b', line):
            continue
        match = re.match(r'^\s*#\s*include\s*(?:"([^"\n]+)"|<([^>\n]+)>)', line)
        if not match:
            raise ValueError('Nonliteral include requires review: ' + path)
        found.append(source_path(path, match[1] or match[2], match[2] is not None))
    return found


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_cache(root, profile):
    receipt = json.loads((root / 'receipt.json').read_text())
    if any(receipt.get(k) != profile[k] for k in ('repository', 'commit', 'entry')):
        raise ValueError('Cache does not match the pinned profile')
    queue = [profile['entry']]
    seen = set()
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        source_path(path, PurePosixPath(path).name, False)
        target = root / path
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('Cache path escapes source root or is a symlink')
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Cache source file exceeds review limit')
        data = target.read_bytes()
        if digest(data) != receipt['files'].get(path):
            raise ValueError('Cache file missing from receipt or changed: ' + path)
        seen.add(path)
        queue.extend(includes(path, data.decode()))
    if seen != set(receipt['files']):
        raise ValueError('Cache receipt must match the complete include graph')
    return receipt


def fetch_graph(root, profile):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', profile['repository']):
        raise ValueError('Invalid repository')
    if not re.fullmatch(r'[0-9a-f]{40}', profile['commit']):
        raise ValueError('Invalid source pin')
    queue = [profile['entry']]
    files = {}
    total = 0
    while queue:
        path = queue.pop()
        if path in files:
            continue
        source_path(path, PurePosixPath(path).name, False)
        if len(files) >= 256:
            raise ValueError('Include graph exceeds review limit')
        url = 'https://raw.githubusercontent.com/' + profile['repository'] + '/' + profile['commit'] + '/' + path
        request = urllib.request.Request(url, headers={'User-Agent': 'pre-asahi-dtb-review'})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        total += len(data)
        if len(data) > 2 * 1024 * 1024 or total > 16 * 1024 * 1024:
            raise ValueError('Source exceeds review size limit')
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[path] = digest(data)
        queue.extend(includes(path, data.decode()))
    receipt = {k: profile[k] for k in ('repository', 'commit', 'entry')}
    receipt['files'] = files
    bringup.save(root / 'receipt.json', receipt)
    return receipt


def property_value(dtb, node, prop):
    result = subprocess.run(['fdtget', '-t', 's', str(dtb), node, prop],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def compile_profile(name, profile, cache):
    bringup.WORK.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='dtb-' + name + '-', dir=bringup.WORK))
    if cache is None:
        cache = attempt / 'source'
        cache.mkdir()
        receipt = fetch_graph(cache, profile)
    else:
        cache = Path(cache).resolve()
        receipt = verify_cache(cache, profile)
    preprocessed = attempt / 'j713.dts'
    dtb = attempt / 'j713.dtb'
    commands = [
        ['clang', '-E', '-P', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
         '-I' + str(cache / 'include'), str(cache / profile['entry']), '-o', str(preprocessed)],
        ['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(dtb), str(preprocessed)],
    ]
    with (attempt / 'build.log').open('w') as log:
        for args in commands:
            bringup.run(args, stdout=log, stderr=subprocess.STDOUT)
    compatible = property_value(dtb, '/', 'compatible')
    if not compatible or 'apple,j713' not in compatible.split() or 'apple,t8132' not in compatible.split():
        raise ValueError('Compiled candidate does not identify j713/T8132')
    names = bringup.capture(['fdtget', '-p', dtb, '/aliases']).splitlines()
    aliases = {}
    for alias in names:
        path = property_value(dtb, '/aliases', alias)
        if path is None:
            raise ValueError('Unresolved DT alias: ' + alias)
        aliases[alias] = {'path': path, 'status_property': property_value(dtb, path, 'status')}
    result = {'status': 'DT_COMPILE_ONLY_NO_DRIVER_OR_HARDWARE_PROOF',
              'profile': name, 'repository': profile['repository'], 'commit': profile['commit'],
              'model': property_value(dtb, '/', 'model'), 'compatible': compatible,
              'source_file_count': len(receipt['files']), 'dtb_bytes': dtb.stat().st_size,
              'dtb_sha256': digest(dtb.read_bytes()), 'aliases': aliases,
              'clang_version': bringup.capture(['clang', '--version']),
              'dtc_version': bringup.capture(['dtc', '--version']),
              'note': 'Aliases/status properties describe source topology, not working peripherals. Full kernel, firmware, bootloader and installation are untested.'}
    bringup.save(attempt / 'result.json', result)
    print('Results and compiler warnings: ' + str(attempt))
    print(json.dumps(result, indent=2))
    return result


def main():
    profiles = json.loads(PROFILES.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=sorted(profiles), required=True)
    parser.add_argument('--offline-cache', type=Path)
    args = parser.parse_args()
    try:
        compile_profile(args.profile, profiles[args.profile], args.offline_cache)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as e:
        print('STOP: ' + str(e), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
