#!/usr/bin/env python3
"""Compile (never execute) a tiny AArch64 object on the development host."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    out = ROOT / 'work/toolchain-check'
    out.mkdir(parents=True, exist_ok=True)
    prefix = os.environ.get('CROSS_COMPILE', 'aarch64-linux-gnu-')
    cc = prefix + 'gcc'
    report = ROOT / 'reports/cross-toolchain.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    if report.exists():
        report.unlink()  # Never leave an old success report after a failed check.
    try:
        version = subprocess.check_output([cc, '--version'], text=True).strip()
        target = subprocess.check_output([cc, '-dumpmachine'], text=True).strip()
        source = out / 'probe.c'
        obj = out / 'probe.o'
        source.write_text('unsigned long phase1_probe(unsigned long x) { return x + 1; }\n')
        subprocess.run([cc, '-ffreestanding', '-fno-stack-protector', '-c', source, '-o', obj], check=True)
        data = obj.read_bytes()
        if (len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or
                struct.unpack_from('<HH', data, 16) != (1, 183)):
            raise ValueError('Compiler did not produce a little-endian AArch64 ELF64 relocatable object')
        result = {'status': 'CROSS_COMPILE_ONLY', 'compiler': cc, 'version': version,
                  'target': target, 'object_sha256': hashlib.sha256(data).hexdigest(),
                  'note': 'No object execution, kernel build, target connection or hardware boot performed.'}
        report.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        print('STOP: ' + str(e), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
