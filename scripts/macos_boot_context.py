#!/usr/bin/env python3
"""Read-only, allowlisted current macOS boot context; never provisions or selects a disk."""
import json
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_REPLY = 4 * 1024 * 1024


def query(command, plist=False):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        if result.returncode or len(result.stdout) > MAX_REPLY:
            return None, 'unavailable'
        return (plistlib.loads(result.stdout) if plist else result.stdout.decode().strip()), 'ok'
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError, plistlib.InvalidFileException):
        return None, 'unavailable'


def safe_text(value, pattern):
    if isinstance(value, bytes):
        try:
            value = value.rstrip(b'\0').decode('ascii')
        except UnicodeError:
            return None
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else None


def number(value):
    if isinstance(value, bytes) and len(value) == 4:
        return int.from_bytes(value, 'little')
    return value if type(value) is int and 0 <= value <= 0xffffffff else None


def chosen_fields(data, known_ids):
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ValueError('Expected exactly one targeted chosen record')
    node = data[0]
    if node.get('IORegistryEntryName') != 'chosen':
        raise ValueError('Unexpected device-tree node')
    result = {'chip_id': number(node.get('chip-id')), 'board_id': number(node.get('board-id'))}
    for key in ['firmware-version', 'system-firmware-version']:
        value = safe_text(node.get(key), r'(?:iBoot|mBoot)-[0-9]+(?:\.[0-9]+){1,8}')
        result[key] = {'id': value, 'recognized_by_pinned_aura_table': value in known_ids if value else None}
    return result


def external_summary(info, index):
    # Never print arbitrary media/volume labels, device identifiers, UUIDs or serials.
    if not isinstance(info, dict) or info.get('Internal') is not False or info.get('Whole') is not True:
        raise ValueError('Expected an external whole device')
    names = [info.get(k) for k in ['MediaName', 'DeviceModel', 'IORegistryEntryName']]
    t7 = any(isinstance(v, str) and re.search(r'\bT7\b', v, re.I) for v in names)
    size = info.get('TotalSize')
    if type(size) is not int or not 0 < size <= 128 * 1024**4:
        size = None
    transport = info.get('BusProtocol')
    if transport not in ['USB', 'Thunderbolt', 'PCI-Express', 'Apple Fabric']:
        transport = 'not reported'
    return {'external_index': index, 't7_name_match': t7, 'bytes': size, 'transport': transport}


def collect(run_query=query):
    refs = json.loads((ROOT / 'configs/native-entry-references.json').read_text())
    pins = json.loads((ROOT / 'configs/candidate-stack.json').read_text())
    if refs['aura']['commit'] != pins['aura_commit']:
        raise ValueError('Aura source pin changed; refresh the firmware-table review')
    model, model_status = run_query(['/usr/sbin/sysctl', '-n', 'hw.model'])
    version, version_status = run_query(['/usr/bin/sw_vers', '-productVersion'])
    build, build_status = run_query(['/usr/bin/sw_vers', '-buildVersion'])
    chosen, chosen_status = run_query(['/usr/sbin/ioreg', '-a', '-p', 'IODeviceTree', '-r', '-n', 'chosen', '-d', '1'], True)
    root, root_status = run_query(['/usr/sbin/diskutil', 'info', '-plist', '/'], True)
    disks, disks_status = run_query(['/usr/sbin/diskutil', 'list', '-plist', 'external', 'physical'], True)
    try:
        fields = chosen_fields(chosen, refs['aura']['firmware_ids'])
    except ValueError:
        fields, chosen_status = None, 'unavailable'
    external = []
    if isinstance(disks, dict) and isinstance(disks.get('AllDisksAndPartitions'), list):
        rows = disks['AllDisksAndPartitions']
        if len(rows) > 8:
            disks_status = 'too_many_devices'
        else:
            seen = set()
            for row in rows:
                identifier = safe_text(row.get('DeviceIdentifier') if isinstance(row, dict) else None, r'disk[0-9]+')
                if not identifier or identifier in seen:
                    disks_status = 'unavailable'; continue
                seen.add(identifier)
                info, status = run_query(['/usr/sbin/diskutil', 'info', '-plist', identifier], True)
                if status != 'ok':
                    disks_status = 'partial'
                    continue
                try:
                    external.append(external_summary(info, len(external) + 1))
                except ValueError:
                    disks_status = 'partial'
    elif disks_status == 'ok':
        disks_status = 'unavailable'
    internal = root.get('Internal') if isinstance(root, dict) else None
    if type(internal) is not bool:
        internal = None
    return {'status': 'READ_ONLY_CURRENT_MACOS_BOOT_CONTEXT', 'native_boot_proven': False,
            'native_entry_qualified': False, 'disk_or_boot_state_changed': False,
            'model': safe_text(model, r'Mac[0-9]+,[0-9]+'),
            'macos_version': safe_text(version, r'[0-9]+(?:\.[0-9]+){1,2}'),
            'macos_build': safe_text(build, r'[0-9A-Za-z]{3,20}'),
            'currently_running_os_boot_context': fields, 'root_storage_internal': internal,
            'external_physical_devices': external,
            'query_status': {'model': model_status, 'version': version_status, 'build': build_status,
                             'chosen': chosen_status, 'root_storage': root_status, 'external_storage': disks_status},
            'aura_firmware_table_revision': refs['aura']['commit'],
            'note': 'Current macOS only, not a future Linux stub. Recognized firmware IDs do not prove compatibility. External indexes are reporting labels, never disk targets. No raw registry/disk report is saved.'}


def main():
    if platform.system() != 'Darwin' or platform.machine() not in ('arm64', 'aarch64'):
        print('STOP: run this read-only probe in native ARM64 macOS', file=sys.stderr)
        return 1
    try:
        print(json.dumps(collect(), indent=2))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print('STOP: boot-context probe unavailable (' + type(error).__name__ + ')', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
