#!/usr/bin/env python3
"""Build a checked BusyBox archive locally. Never installs or boots it."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import bringup

VERSION = '1.38.0'
SHA256 = '34f9ea6ff8636f2c9241153b9114eefa9e65674a45318ae1ef95bb5f31c53bb2'
REQUIRED_APPLETS = {'sh', 'mount', 'uname', 'tr', 'sleep'}

def checked_members(archive):
    members = archive.getmembers()
    for item in members:
        path = PurePosixPath(item.name)
        if (not path.parts or path.parts[0] != 'busybox-' + VERSION or
                path.is_absolute() or '..' in path.parts or
                not (item.isfile() or item.isdir())):
            raise ValueError('Unsafe or unexpected archive entry: ' + item.name)
    return members

def build(archive_path):
    if platform.system() != 'Linux':
        raise ValueError('Use the Linux build host for BusyBox')
    archive_path = Path(archive_path).resolve()
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != SHA256:
        raise ValueError('BusyBox archive checksum mismatch')
    # Keep each attempt and its sources for inspection; never reuse a modified source tree.
    bringup.WORK.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='busybox-attempt-', dir=bringup.WORK))
    print('Build attempt retained at: ' + str(attempt), flush=True)
    with tarfile.open(archive_path) as archive:
        archive.extractall(attempt, members=checked_members(archive))
    src = attempt / ('busybox-' + VERSION)
    out = attempt / 'build'
    out.mkdir()
    prefix = os.environ.get('CROSS_COMPILE', 'aarch64-linux-gnu-')
    compiler = bringup.capture([prefix + 'gcc', '--version'])
    fragment = bringup.ROOT / 'configs/busybox.config'
    base = ['make', '-C', src, 'O=' + str(out), 'CROSS_COMPILE=' + prefix]
    bringup.run(base + ['allnoconfig'])
    # BusyBox's allnoconfig resets boolean selections even with KCONFIG_ALLCONFIG.
    # Overlay the requested values, then use defconfig to resolve dependencies.
    requested = (out / '.config').read_text().splitlines()
    for line in fragment.read_text().splitlines():
        if not line.startswith('CONFIG_'):
            continue
        key = line.split('=', 1)[0]
        requested = [x for x in requested if not x.startswith(key + '=') and
                     x != '# ' + key + ' is not set']
        requested.append(line)
    seed = attempt / 'requested.config'
    seed.write_text('\n'.join(requested) + '\n')
    bringup.run(base + ['KBUILD_DEFCONFIG=' + str(seed), 'defconfig'])
    resolved = (out / '.config').read_text().splitlines()
    required = [x for x in fragment.read_text().splitlines() if x.startswith('CONFIG_')]
    missing = [x for x in required if x not in resolved]
    if missing:
        raise ValueError('BusyBox config not resolved: ' + ', '.join(missing))
    bringup.run(base + ['-j' + str(min(os.cpu_count() or 1, 8))])
    binary = out / 'busybox'
    data = binary.read_bytes()
    bringup.validate_busybox(data)
    # Explicit QEMU calls only; no binfmt registration and no /init execution.
    applets = set(bringup.capture(['qemu-aarch64', binary, '--list']).splitlines())
    if not REQUIRED_APPLETS <= applets:
        raise ValueError('Missing BusyBox applets: ' + ', '.join(sorted(REQUIRED_APPLETS - applets)))
    marker = bringup.capture(['qemu-aarch64', binary, 'sh', '-c', 'if [ -r /dev/null ]; then echo BUSYBOX_AARCH64_OK; else exit 1; fi'])
    if marker != 'BUSYBOX_AARCH64_OK':
        raise ValueError('BusyBox shell smoke test failed')
    dest = bringup.WORK / 'artifacts'
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / '.config', dest / 'busybox.config')
    shutil.copy2(binary, dest / 'busybox')
    bringup.save(dest / 'busybox-build.json', {
        'status': 'USERSPACE_SMOKE_ONLY_NO_KERNEL_BOOT', 'version': VERSION,
        'source_url': 'https://www.busybox.net/downloads/busybox-' + VERSION + '.tar.bz2',
        'archive_sha256': SHA256, 'binary_sha256': hashlib.sha256(data).hexdigest(),
        'config_sha256': hashlib.sha256((out / '.config').read_bytes()).hexdigest(),
        'compiler': compiler, 'qemu_version': bringup.capture(['qemu-aarch64', '--version']),
        'required_applets': sorted(REQUIRED_APPLETS), 'smoke_marker': marker})
    bringup.initramfs(dest / 'busybox')
    print('BusyBox and diagnostic initramfs prepared. No kernel or hardware boot was tested.')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', required=True)
    args = p.parse_args()
    try:
        build(args.archive)
    except (OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as e:
        print('STOP: ' + str(e), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
