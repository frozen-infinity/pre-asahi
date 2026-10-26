#!/usr/bin/env python3
"""Local preparation only. No hardware boot or disk-management operations."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
REPORTS = ROOT / 'reports'
REPOS = {'m1n1': ('https://github.com/AsahiLinux/m1n1.git', 'main'),
         'linux': ('https://github.com/AsahiLinux/linux.git', 'asahi')}
LOCK = ROOT / 'sources.lock.json'
INIT = b'''#!/bin/busybox sh
export PATH=/bin
/bin/busybox mount -t proc proc /proc || exit 1
/bin/busybox mount -t sysfs sysfs /sys || exit 1
/bin/busybox mount -t devtmpfs devtmpfs /dev || exit 1
echo M4AIR_PHASE1_PID1
/bin/busybox uname -a
if [ -r /sys/firmware/devicetree/base/compatible ]; then
    /bin/busybox tr '\\000' '\\n' < /sys/firmware/devicetree/base/compatible
fi
while :; do /bin/busybox sleep 60; done
'''

def run(args, **kw):
    return subprocess.run([str(a) for a in args], check=True, **kw)

def capture(args):
    return run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')

def probe(args):
    try:
        return {'value': capture(args)}
    except (OSError, subprocess.CalledProcessError) as e:
        return {'unavailable': str(e)}

def identify():
    data = {'system': platform.system(), 'architecture': platform.machine()}
    if platform.system() == 'Darwin':
        for key in ['hw.model', 'machdep.cpu.brand_string', 'hw.memsize']:
            data[key] = probe(['/usr/sbin/sysctl', '-n', key])
        data['os'] = probe(['/usr/bin/sw_vers'])
    model = data.get('hw.model', {}).get('value')
    data['candidate_board'] = {'Mac16,12': 'j713', 'Mac16,13': 'j715'}.get(model)
    data['hardware_boot_authorized'] = False
    save(REPORTS / 'hardware.json', data)
    print(json.dumps(data, indent=2))

def doctor():
    names = ['git', 'make', 'python3', 'rustc', 'cargo', 'rustup', 'clang',
             'ld.lld', 'llvm-objcopy', 'dtc', 'magick', 'convert',
             'aarch64-linux-gnu-gcc', 'bc', 'bison', 'flex', 'pkg-config', 'gzip']
    data = {'system': platform.system(), 'tools': {x: shutil.which(x) for x in names},
            'note': 'Presence only; missing dependencies are not installed automatically.'}
    save(REPORTS / 'doctor.json', data)
    print(json.dumps(data, indent=2))

def read_lock():
    data = json.loads(LOCK.read_text())
    if set(data) != set(REPOS):
        raise ValueError('Unexpected repositories in source lock')
    for name, (url, branch) in REPOS.items():
        entry = data[name]
        if entry['url'] != url or entry['branch'] != branch or len(entry['commit']) != 40:
            raise ValueError('Invalid source lock')
        int(entry['commit'], 16)
    return data

def checked_source(name, lock):
    src = WORK / 'src' / name
    if capture(['git', '-C', src, 'remote', 'get-url', 'origin']) != lock[name]['url']:
        raise ValueError('Remote mismatch: ' + name)
    if capture(['git', '-C', src, 'rev-parse', 'HEAD']) != lock[name]['commit']:
        raise ValueError('Commit mismatch: ' + name)
    if capture(['git', '-C', src, 'status', '--porcelain', '--untracked-files=no']):
        raise ValueError('Dirty tracked source: ' + name)
    return src

def fetch():
    if LOCK.exists():
        lock = read_lock()
    else:
        lock = {}
        for name, (url, branch) in REPOS.items():
            sha = capture(['git', 'ls-remote', '--exit-code', url, 'refs/heads/' + branch]).split()[0]
            if len(sha) != 40:
                raise ValueError('Unexpected commit ID')
            lock[name] = {'url': url, 'branch': branch, 'commit': sha}
        save(LOCK, lock)
    for name, entry in lock.items():
        src = WORK / 'src' / name
        if not src.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            run(['git', 'init', src])
            run(['git', '-C', src, 'remote', 'add', 'origin', entry['url']])
            run(['git', '-C', src, 'fetch', '--depth=1', 'origin', entry['commit']])
            run(['git', '-C', src, 'checkout', '--detach', entry['commit']])
        checked_source(name, lock)
        if name == 'm1n1':
            run(['git', '-C', src, 'submodule', 'update', '--init', '--recursive'])
    print('Pinned source checkouts ready. Review them before building.')

def build_m1n1():
    src = checked_source('m1n1', read_lock())
    status = run(['git', '-C', src, 'submodule', 'status', '--recursive'],
                 stdout=subprocess.PIPE, text=True).stdout
    if any(line and line[0] != ' ' for line in status.splitlines()):
        raise ValueError('Missing or mismatched m1n1 submodules')
    run(['make', '-C', src, '-j' + str(min(os.cpu_count() or 1, 8))])
    for name in ['m1n1.bin', 'm1n1.macho']:
        if not (src / 'build' / name).is_file():
            raise ValueError('Missing m1n1 output: ' + name)

def build_linux(model):
    if platform.system() != 'Linux':
        raise ValueError('Build Linux on a Linux host with an AArch64 cross toolchain; see README.')
    src = checked_source('linux', read_lock())
    out = WORK / 'build' / model
    out.mkdir(parents=True, exist_ok=True)
    cross = os.environ.get('CROSS_COMPILE', 'aarch64-linux-gnu-')
    base = ['make', '-C', src, 'O=' + str(out), 'ARCH=arm64', 'CROSS_COMPILE=' + cross]
    run(base + ['defconfig'])
    run(['bash', src / 'scripts/kconfig/merge_config.sh', '-m', '-O', out,
         out / '.config', ROOT / 'configs/phase1.config'], cwd=src)
    run(base + ['olddefconfig'])
    config = (out / '.config').read_text().splitlines()
    required = [x for x in (ROOT / 'configs/phase1.config').read_text().splitlines()
                if x.startswith('CONFIG_') or x.endswith(' is not set')]
    missing = [x for x in required if x not in config]
    if missing:
        raise ValueError('Unresolved required config: ' + ', '.join(missing))
    run(base + ['-j' + str(min(os.cpu_count() or 1, 8)), 'Image',
                'apple/t8132-' + model + '.dtb'])
    image = out / 'arch/arm64/boot/Image'
    with (image.parent / 'Image.gz').open('wb') as f:
        with gzip.GzipFile(filename='', mode='wb', fileobj=f, mtime=0) as z:
            with image.open('rb') as r:
                shutil.copyfileobj(r, z)
    save(out / 'toolchain.json', {'gcc': capture([cross + 'gcc', '--version'])})

def validate_busybox(data):
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected little-endian ELF64 BusyBox')
    if struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('Expected AArch64 executable')
    if struct.unpack_from('<H', data, 16)[0] not in (2, 3):
        raise ValueError('Expected executable ELF type')
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    if not count or size < 56 or offset + size * count > len(data):
        raise ValueError('Invalid ELF program headers')
    types = [struct.unpack_from('<I', data, offset + size * i)[0] for i in range(count)]
    if 3 in types or 2 in types:
        raise ValueError('Dynamic ELF unsupported; supply a conventional static BusyBox')
    if 1 not in types:
        raise ValueError('No ELF load segment')

def newc(entries):
    out = bytearray()
    for inode, entry in enumerate(entries + [('TRAILER!!!', 0, b'')], 1):
        name, mode, data = entry[:3]
        rmajor, rminor = entry[3:] if len(entry) == 5 else (0, 0)
        encoded = name.encode() + b'\0'
        fields = [inode, mode, 0, 0, 1, 0, len(data), 0, 0, rmajor, rminor, len(encoded), 0]
        out.extend(b'070701' + ''.join('%08x' % v for v in fields).encode() + encoded)
        out.extend(b'\0' * (-len(out) % 4))
        out.extend(data)
        out.extend(b'\0' * (-len(out) % 4))
    out.extend(b'\0' * (-len(out) % 512))
    return bytes(out)

def initramfs(binary):
    data = Path(binary).read_bytes()
    validate_busybox(data)
    dirs = [(x, 0o40755, b'') for x in ['bin', 'dev', 'proc', 'sys', 'tmp']]
    archive = newc(dirs + [('dev/console', 0o20600, b'', 5, 1), ('bin/busybox', 0o100755, data), ('init', 0o100755, INIT)])
    out = WORK / 'artifacts/initramfs.cpio.gz'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('wb') as f:
        with gzip.GzipFile(filename='', mode='wb', fileobj=f, mtime=0) as z:
            z.write(archive)
    print(out)

def manifest():
    result = {'status': 'PREPARATION_ONLY_NO_BOOT_PROOF', 'sha256': {}}
    paths = []
    if LOCK.exists():
        read_lock()
        paths.append(LOCK)
    for parent in [WORK / 'artifacts', WORK / 'build', WORK / 'src/m1n1/build']:
        if parent.exists():
            paths.extend(x for x in parent.rglob('*') if x.is_file() and
                         (x.name in ['Image', 'Image.gz', '.config', 'm1n1.bin', 'm1n1.macho',
                                     'initramfs.cpio.gz', 'toolchain.json', 'busybox', 'busybox.config', 'busybox-build.json'] or x.suffix == '.dtb'))
    for path in paths:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        result['sha256'][str(path.relative_to(ROOT))] = h.hexdigest()
    if not paths:
        raise ValueError('No source lock or build artifacts to record')
    save(REPORTS / 'manifest.json', result)
    print('Manifest records available files only; it is not a boot-readiness verdict.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['identify', 'doctor', 'fetch', 'build-m1n1', 'manifest']:
        sub.add_parser(name)
    sub.add_parser('build-linux').add_argument('--model', choices=['j713', 'j715'], required=True)
    sub.add_parser('initramfs').add_argument('--busybox', required=True)
    args = parser.parse_args()
    actions = {'identify': identify, 'doctor': doctor, 'fetch': fetch, 'build-m1n1': build_m1n1,
               'manifest': manifest, 'build-linux': lambda: build_linux(args.model),
               'initramfs': lambda: initramfs(args.busybox)}
    try:
        actions[args.command]()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as e:
        print('STOP: ' + str(e), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
