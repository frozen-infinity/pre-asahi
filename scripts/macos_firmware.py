#!/usr/bin/env python3
"""Print only allowlisted macOS hardware/firmware fields; change no boot state."""
import json
import platform
import subprocess
import sys

FIELDS = ('machine_model', 'chip_type', 'boot_rom_version',
          'system_firmware_version', 'os_loader_version')

def filtered_report(data):
    hardware = data.get('SPHardwareDataType', [])
    if not hardware or not isinstance(hardware[0], dict):
        raise ValueError('No hardware record returned')
    return {'status': 'IDENTIFICATION_ONLY_NO_BOOT_APPROVAL',
            'fields': {key: hardware[0].get(key, 'not reported') for key in FIELDS}}

def main():
    if platform.system() != 'Darwin':
        print('STOP: run this read-only report on the Mac in macOS', file=sys.stderr)
        return 1
    try:
        result = subprocess.run(['/usr/sbin/system_profiler', 'SPHardwareDataType', '-json'],
                                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=60)
        print(json.dumps(filtered_report(json.loads(result.stdout)), indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        print('STOP: firmware report unavailable (' + type(e).__name__ + ')', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
