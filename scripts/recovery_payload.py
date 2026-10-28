#!/usr/bin/env python3
"""Stage and validate the exact J713 recovery image. Never installs or enrolls."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
import recovery_metadata as metadata

ENCRYPTED_SHA = '12919ca28b831ec9ff71291ac857a51cef54263f4846180c7b7311a58c51d13e'
DECODED_SHA = 'c7e05c0261a687b256c9ee58341346fbb995dfd04f03affd874524e6bc2e615d'
ENCRYPTED_BYTES = 1140850688
# Apple-published release key from the pinned downstream J713 recovery profile.
KEY = 'base64:jwTzZTlYzWR0hJi0ISUdhMp39bmqC112h34G5qV6PDM='
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def download(attempt):
    target = attempt / 'BaseSystem.dmg.aea'
    if target.exists():
        metadata.require(target.is_file() and not target.is_symlink() and
                         target.stat().st_size == ENCRYPTED_BYTES and digest(target) == ENCRYPTED_SHA,
                         'Cached encrypted recovery does not match the exact profile')
        return target
    partial = attempt / 'BaseSystem.dmg.aea.partial'
    metadata.require(not partial.exists(), 'Partial download exists; review/remove it before retrying')
    with metadata.RangeArchive(transfer_limit=2 * 1024**3, request_limit=1024) as source:
        report = metadata.inspect(source)
        with zipfile.ZipFile(source) as archive:
            items = [i for i in archive.infolist() if i.filename == metadata.RECOVERY]
            metadata.require(len(items) == 1 and items[0].file_size == ENCRYPTED_BYTES and
                             items[0].compress_size <= ENCRYPTED_BYTES + 16 * 1024**2,
                             'Unexpected recovery ZIP geometry')
            h = hashlib.sha256()
            count = 0
            with archive.open(items[0]) as src, partial.open('xb') as out:
                while True:
                    block = src.read(4 * 1024**2)
                    if not block:
                        break
                    count += len(block)
                    metadata.require(count <= ENCRYPTED_BYTES, 'Recovery exceeds pinned size')
                    h.update(block)
                    out.write(block)
                    if count // (128 * 1024**2) != (count - len(block)) // (128 * 1024**2):
                        print(f'Recovery staged: {count // 1024**2} MiB', flush=True)
            metadata.require(count == ENCRYPTED_BYTES and h.hexdigest() == ENCRYPTED_SHA,
                             'Encrypted recovery SHA-256/size mismatch')
        report.update(metadata_transfer_bytes=source.transferred, range_requests=source.requests)
    partial.rename(target)
    (attempt / 'archive-metadata.json').write_text(json.dumps(report, indent=2) + '\n')
    return target


def decode(attempt, encrypted):
    target = attempt / 'BaseSystem.dmg'
    if target.exists():
        metadata.require(not target.is_symlink() and target.is_file() and digest(target) == DECODED_SHA,
                         'Cached decoded recovery does not match the exact profile')
        return target
    partial = attempt / 'BaseSystem.partial.dmg'
    key = attempt / 'release.key'
    metadata.require(not partial.exists() and not key.exists(), 'Decode scratch file already exists')
    try:
        with key.open('x') as output:
            output.write(KEY)
        key.chmod(0o600)
        subprocess.run(['/usr/bin/aea', 'decrypt', '-i', str(encrypted), '-o', str(partial),
                        '-key', str(key)], check=True, timeout=300)
        metadata.require(partial.is_file() and digest(partial) == DECODED_SHA,
                         'Decoded recovery SHA-256 mismatch')
        subprocess.run(['/usr/bin/hdiutil', 'verify', str(partial)], check=True, timeout=300)
        partial.rename(target)
    finally:
        key.unlink(missing_ok=True)
    return target


def inspect_mount(mount):
    with (mount / 'System/Library/CoreServices/SystemVersion.plist').open('rb') as stream:
        version = plistlib.load(stream)
    metadata.require(version.get('ProductVersion') == '26.5.1' and
                     version.get('ProductBuildVersion') == '25F80', 'Mounted recovery version mismatch')
    tools = {}
    for tool in ['kmutil', 'bputil', 'bless', 'diskutil', 'sh']:
        matches = [p for directory in ['usr/bin', 'usr/sbin', 'bin', 'sbin']
                   if (p := mount / directory / tool).is_file() and
                   p.resolve().is_relative_to(mount.resolve())]
        metadata.require(bool(matches), 'Missing recovery tool: ' + tool)
        tools[tool] = str(matches[0].relative_to(mount))
    return {'version': version['ProductVersion'], 'build': version['ProductBuildVersion'],
            'tools_present_not_executed': tools}


def attached_device(image):
    query = subprocess.run(['/usr/bin/hdiutil', 'info', '-plist'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    images = [i for i in plistlib.loads(query.stdout).get('images', [])
              if i.get('image-path') == str(image)]
    metadata.require(len(images) <= 1, 'Ambiguous task-created image attachment')
    if not images:
        return None
    entities = images[0].get('system-entities', [])
    metadata.require(entities and entities[0].get('content-hint') == 'GUID_partition_scheme',
                     'Unexpected task-created disk-image geometry')
    return entities[0]['dev-entry']


def validate(attempt):
    metadata.require(platform.system() == 'Darwin' and platform.machine() == 'arm64',
                     'Native macOS ARM64 is required for recovery decoding and inspection')
    metadata.require(shutil.disk_usage(attempt).free >= 5 * 1024**3, 'Need at least 5 GiB scratch space')
    encrypted = download(attempt)
    print('Encrypted recovery hash verified', flush=True)
    image = decode(attempt, encrypted)
    print('Decoded recovery hash and image integrity verified', flush=True)
    mount = attempt / 'mount'
    mount.mkdir(exist_ok=False)
    # A mounted filesystem can stall a file read; keep inspection in a child
    # with a deadline instead of letting an unbounded Path.read_bytes hang us.
    failure = {'status': 'RECOVERY_HASH_AND_IMAGE_VERIFY_PASS_CONTENT_INSPECTION_PENDING',
               'encrypted_sha256': ENCRYPTED_SHA, 'decoded_sha256': DECODED_SHA,
               'native_entry_qualified': False, 'native_boot_proven': False}
    (attempt / 'inspection-state.json').write_text(json.dumps(failure, indent=2) + '\n')
    try:
        subprocess.run(['/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse',
                        '-mountpoint', str(mount), str(image)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        code = ('import json,sys; from pathlib import Path; from recovery_payload import inspect_mount; '
                'print(json.dumps(inspect_mount(Path(sys.argv[1]))))')
        inspected = subprocess.run([sys.executable, '-c', code, str(mount)],
                                   cwd=Path(__file__).resolve().parent,
                                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        contents = json.loads(inspected.stdout)
    except BaseException:
        failure['status'] = 'RECOVERY_HASH_PASS_CONTENT_INSPECTION_FAILED'
        (attempt / 'inspection-state.json').write_text(json.dumps(failure, indent=2) + '\n')
        raise
    finally:
        # Also attempt cleanup after attach errors/timeouts: attachment may have
        # completed in the system service despite the client failing.
        # Resolve only through hdiutil's image inventory; a stalled filesystem
        # path must not be consulted to choose an eject target.
        device = attached_device(image)
        if device:
            detached = subprocess.run(['/usr/bin/hdiutil', 'detach', device],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if detached.returncode:
                raise RuntimeError('Read-only image detach failed; inspect this scratch image before retrying')
        # Never remove mount contents; an unsuccessful detach needs manual review.
        try:
            mount.rmdir()
        except OSError:
            pass
    result = {'status': 'J713_RECOVERY_IMAGE_INSPECTION_ONLY_PASS',
              'installer_base': metadata.INSTALLER, 'downstream_profile': metadata.PROFILE,
              'encrypted_sha256': ENCRYPTED_SHA, 'decoded_sha256': DECODED_SHA,
              'read_only_mount_inspected_and_detached': True, 'contents': contents,
              'installer_executed': False, 'boot_policy_changed': False,
              'physical_disk_layout_changed': False, 'host_boot_compatibility_qualified': False,
              'native_entry_qualified': False, 'native_boot_proven': False,
              'note': 'Apple image files staged/decoded and read-only mounted; no installer, '
                      'personalization, enrollment or recovery binaries were executed.'}
    (attempt / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path,
                        help='Reuse an existing scratch directory after checking every cached image hash')
    args = parser.parse_args()
    parent = ROOT / 'work/recovery-payload'
    parent.mkdir(parents=True, exist_ok=True)
    attempt = args.attempt.resolve() if args.attempt else Path(tempfile.mkdtemp(prefix='attempt-', dir=parent))
    metadata.require(attempt.parent == parent.resolve() and attempt.is_dir() and not attempt.is_symlink(),
                     'Attempt must be an existing direct child of the project recovery scratch directory')
    print('Recovery scratch: ' + str(attempt), flush=True)
    validate(attempt)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        raise SystemExit('STOP: ' + str(error))
