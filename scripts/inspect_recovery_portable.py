#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check one exact Apple recovery DMG on a second Mac. Never installs or enrolls."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys
import tempfile
import time

IMAGE_SHA = 'c7e05c0261a687b256c9ee58341346fbb995dfd04f03affd874524e6bc2e615d'
IMAGE_BYTES = 1560927608


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(image):
    require(image.is_file() and not image.is_symlink() and image.stat().st_size == IMAGE_BYTES,
            'Wrong or missing recovery image; expected the exact decoded 25F80 DMG')
    h = hashlib.sha256()
    with image.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    require(h.hexdigest() == IMAGE_SHA, 'Recovery image SHA-256 mismatch')


def command(args, timeout):
    result = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout, check=True)
    require(len(result.stdout) <= 4 * 1024**2, 'Unexpectedly large command response')
    return result.stdout


def device_for(image, run=command):
    data = plistlib.loads(run(['/usr/bin/hdiutil', 'info', '-plist'], 20))
    matches = [row for row in data.get('images', []) if row.get('image-path') == str(image)]
    require(len(matches) <= 1, 'Ambiguous image attachment')
    if not matches:
        return None
    entities = matches[0].get('system-entities', [])
    require(entities and entities[0].get('content-hint') == 'GUID_partition_scheme',
            'Unexpected image-device geometry')
    device = entities[0].get('dev-entry', '')
    require(re.fullmatch(r'/dev/disk[0-9]+', device), 'Unexpected image-device identifier')
    return device


def read_contents(root):
    version_file = root / 'System/Library/CoreServices/SystemVersion.plist'
    require(version_file.resolve().is_relative_to(root.resolve()), 'Version file escapes image')
    with version_file.open('rb') as stream:
        version = plistlib.load(stream)
    require(version.get('ProductVersion') == '26.5.1' and
            version.get('ProductBuildVersion') == '25F80', 'Unexpected recovery version/build')
    tools = {}
    for tool in ['kmutil', 'bputil', 'bless', 'diskutil', 'sh']:
        paths = [root / folder / tool for folder in ['usr/bin', 'usr/sbin', 'bin', 'sbin']]
        paths = [p for p in paths if p.is_file() and p.resolve().is_relative_to(root.resolve())]
        require(paths, 'Recovery tool not found: ' + tool)
        tools[tool] = str(paths[0].relative_to(root))
    return {'version': '26.5.1', 'build': '25F80', 'tools_present_not_executed': tools}


def inspect(image, run=command):
    require(platform.system() == 'Darwin', 'Content inspection requires macOS')
    verify(image)  # No image/device command before the exact file has been checked.
    require(device_for(image, run) is None, 'Image already attached; do not detach another session')
    mount = Path(tempfile.mkdtemp(prefix='pre-asahi-recovery-inspection-'))
    result = {'status': 'RECOVERY_CONTENT_INSPECTION_FAILED', 'image_sha256': IMAGE_SHA,
              'host_architecture': platform.machine(), 'contents': None,
              'cleanup_confirmed': False, 'installer_executed': False,
              'boot_policy_changed': False, 'native_boot_proven': False,
              'external_boot_qualified': False, 'error_stage': None}
    stage = 'attach_readonly'
    try:
        run(['/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', mount, image], 120)
        stage = 'read_contents'
        # File reads on the M4 stalled. A separate child bounds their lifetime.
        reply = run([sys.executable, Path(__file__).resolve(), '--read-mounted', mount], 30)
        result['contents'] = json.loads(reply)
        require(result['contents'].get('version') == '26.5.1' and
                result['contents'].get('build') == '25F80', 'Child returned wrong recovery version')
        result['status'] = 'RECOVERY_CONTENT_INSPECTION_ONLY_PASS'
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        result['error_stage'] = stage
    finally:
        try:
            device = device_for(image, run)
            if device:
                # Device is resolved from this exact image, not from the T7 or
                # a filesystem path that may itself be blocked. Never force eject.
                run(['/usr/sbin/diskutil', 'eject', device], 30)
            result['cleanup_confirmed'] = device_for(image, run) is None
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            result['cleanup_confirmed'] = False
        if not result['cleanup_confirmed']:
            result['status'] = 'RECOVERY_INSPECTION_CLEANUP_UNCONFIRMED'
            result['error_stage'] = 'image_cleanup'
        else:
            try:
                mount.rmdir()
            except OSError:
                pass  # Never delete contents of an unexpected directory.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', action='store_true', help='Attempt the read-only mount/content check on the borrowed Mac')
    parser.add_argument('--read-mounted', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.read_mounted:
        print(json.dumps(read_contents(args.read_mounted)))
        return 0
    image = Path(__file__).resolve().parent / 'BaseSystem.dmg'
    verify(image)
    if not args.inspect:
        print(json.dumps({'status': 'TRANSFERRED_RECOVERY_HASH_ONLY_PASS', 'image_sha256': IMAGE_SHA,
                          'contents_inspected': False, 'image_mounted': False, 'native_boot_proven': False}, indent=2))
        return 0
    print('Exact image verified. Beginning bounded read-only inspection.', flush=True)
    result = inspect(image)
    result['host_macos_version'] = platform.mac_ver()[0] or None
    output = image.parent / ('inspection-' + time.strftime('%Y%m%d-%H%M%S', time.gmtime()) + '.json')
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    print('Report: ' + str(output))
    return 0 if result['status'] == 'RECOVERY_CONTENT_INSPECTION_ONLY_PASS' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('STOP: ' + str(error))
