#!/usr/bin/env python3
"""Build a separate unqualified Aura proxy-only first-entry candidate. Never installs or boots."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import shlex
import struct
import subprocess
import sys
import tempfile
import bringup
from qemu_kernel import sha256

RUST = '1.99.0'
TAG = 'pre-asahi-stage1-proxy-553b566f6927'
PIN = '553b566f69275ff4e46ee6542a7236fb80a333a2'
EXTRA_FLAGS = '-DNO_DISPLAY'
FORBIDDEN = ['CHAINLOADING', 'RELEASE', 'ESP_STAGE2', 'BRINGUP',
             'J613_ESP_STAGE1', 'FB_SILENT_MODE', 'USE_DEBUG_USB', 'EARLY_PROXY_TIMEOUT']


def macro_contract(text):
    names = {line.split()[1] for line in text.splitlines() if line.startswith('#define ') and len(line.split()) >= 2}
    if not {'NO_DISPLAY', 'USE_FB'} <= names or any(name in names for name in FORBIDDEN):
        raise ValueError('Proxy-only effective configuration did not resolve')
    return {'present': ['NO_DISPLAY', 'USE_FB'], 'absent': FORBIDDEN}


def compilation_contract(text):
    commands = []
    for line in text.splitlines():
        if 'clang ' not in line or ' -c ' not in line:
            continue
        tokens = shlex.split(line)
        if tokens and Path(tokens[0]).name == 'clang' and '-c' in tokens and any(t.endswith('.c') for t in tokens):
            commands.append(tokens)
    if (not commands or any(EXTRA_FLAGS not in command for command in commands) or
            not all(any(source in command for command in commands) for source in ['src/main.c', 'src/display.c'])):
        raise ValueError('Actual Aura C commands lack the required NO_DISPLAY profile')
    return len(commands)


def raw_contract(data, elf_header):
    if not 4096 <= len(data) <= 16 * 1024 * 1024 or not data.endswith(b'STACKBOT'):
        raise ValueError('Expected bounded bare Aura image ending at STACKBOT')
    if b'AURORA-S1-CFG01' in data:
        raise ValueError('Unexpected embedded ESP Stage-1 configuration')
    marker = b'##m1n1_ver##' + TAG.encode() + b'\0'
    if data.count(marker) != 1:
        raise ValueError('Candidate version tag mismatch')
    if (len(elf_header) < 64 or elf_header[:6] != b'\x7fELF\x02\x01' or
            struct.unpack_from('<H', elf_header, 18)[0] != 183 or
            struct.unpack_from('<Q', elf_header, 24)[0] != 2048):
        raise ValueError('Expected AArch64 raw ELF with entry offset 2048')


def empty_boot_object(raw):
    # Matches the reviewed installer's empty-variable registration layout.
    # The zero terminator prevents payload scanning from reading beyond this object.
    return raw + bytes(4 + (-(len(raw) + 4)) % 65536)


def boot_object_contract(raw, candidate):
    expected = (len(raw) + 4 + 65535) // 65536 * 65536
    if (len(candidate) != expected or candidate[:len(raw)] != raw or
            any(candidate[len(raw):])):
        raise ValueError('Boot object must contain only the bare image and zero terminator/padding')


def build(args):
    if platform.system() != 'Linux':
        raise ValueError('Use the Linux build host or disposable CI runner for this profile')
    pins = json.loads((bringup.ROOT / 'configs/candidate-stack.json').read_text())
    if pins['aura_commit'] != PIN:
        raise ValueError('Aura pin changed; review the proxy-only profile first')
    llvm = Path(args.llvm_dir).resolve()
    for name in ['clang', 'ld.lld', 'llvm-objcopy']:
        if not (llvm / name).is_file():
            raise ValueError('Missing LLVM tool: ' + name)
    for name in ['git', 'make', 'rustup']:
        if not shutil.which(name):
            raise ValueError('Missing build tool: ' + name)
    rust_version = bringup.capture(['rustup', 'run', RUST, 'rustc', '--version'])
    if not rust_version.startswith('rustc ' + RUST + ' '):
        raise ValueError('Wrong Rust toolchain')
    targets = bringup.capture(['rustup', 'target', 'list', '--installed', '--toolchain', RUST]).splitlines()
    if 'aarch64-unknown-none-softfloat' not in targets:
        raise ValueError('Install the pinned Rust bare-metal target before building')
    parent = bringup.WORK / 'stage1-proxy'
    parent.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=parent))
    source = attempt / 'source'
    bringup.run(['git', 'init', source])
    bringup.run(['git', '-C', source, 'remote', 'add', 'origin', 'https://github.com/aurora-silicon/aura.git'])
    bringup.run(['git', '-C', source, 'fetch', '--depth=1', 'origin', PIN])
    bringup.run(['git', '-C', source, 'checkout', '--detach', PIN])
    if bringup.capture(['git', '-C', source, 'rev-parse', 'HEAD']) != PIN:
        raise ValueError('Wrong Aura revision')
    environment = dict(os.environ)
    for name in ['MAKEFLAGS', 'MFLAGS', 'MAKEOVERRIDES', 'AURA_VERSION_TAG', 'M1N1_VERSION_TAG',
                 'RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS']:
        environment.pop(name, None)
    environment.update({'RUSTUP_TOOLCHAIN': RUST, 'AURA_VERSION_TAG': TAG,
                        'CARGO_HOME': str(attempt / 'cargo-home')})
    command = ['make', '-C', source, '-j' + str(args.jobs), 'USE_CLANG=1',
               'ARCH=aarch64-linux-gnu', 'TOOLCHAIN=' + str(llvm) + '/',
               'LLDDIR=' + str(llvm) + '/', 'RELEASE=0', 'CHAINLOADING=0', 'ESP_STAGE2=0',
               'J613_ESP_STAGE1=0', 'LOGO=', 'BUILTIN_LOGO=aurora',
               'EXTRA_CFLAGS=' + EXTRA_FLAGS, 'CARGO_FLAGS=--locked', 'V=1', 'build/aura.bin']
    log = attempt / 'build.log'
    with log.open('wb') as output:
        result = subprocess.run([str(x) for x in command], env=environment, stdout=output,
                                stderr=subprocess.STDOUT, timeout=600)
    if result.returncode:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-70:]))
        raise ValueError('Proxy-only Aura build failed; see ' + str(log))
    if bringup.capture(['git', '-C', source, 'status', '--porcelain', '--untracked-files=no']):
        raise ValueError('Build changed tracked Aura sources')
    macro_command = [llvm / 'clang', '--target=aarch64-linux-gnu', EXTRA_FLAGS,
                     '-dM', '-E', '-x', 'c', '-include', source / 'build/build_cfg.h',
                     '-include', source / 'config.h', '/dev/null']
    macros = bringup.capture(macro_command)
    (attempt / 'effective-macros.txt').write_text(macros + '\n')
    contract = macro_contract(macros)
    # Verify the actual C compilation log carries the flag, not just our later macro query.
    compiled_units = compilation_contract(log.read_text(errors='replace'))
    raw = source / 'build/aura.bin'
    elf = source / 'build/aura-raw.elf'
    data = raw.read_bytes()
    raw_contract(data, elf.read_bytes()[:64])
    candidate = attempt / 'UNQUALIFIED-stage1-proxy-REVIEW-ONLY.bin'
    candidate.write_bytes(empty_boot_object(data))
    boot_object_contract(data, candidate.read_bytes())
    report = {'status': 'STAGE1_PROXY_BUILD_ONLY_PASS', 'aura_commit': PIN,
              'profile': 'development proxy only; NO_DISPLAY; no chainload or appended payload',
              'build_tag': TAG, 'effective_configuration': contract, 'checked_c_compilation_commands': compiled_units,
              'native_entry_qualified': False, 'native_boot_proven': False,
              'target_execution_performed': False, 'installed_boot_objects_changed': False,
              'kernel_or_dtb_appended': False, 'embedded_esp_target_present': False,
              'raw_entry_offset': 2048, 'registration_alignment': 65536,
              'raw_image_bytes': len(data), 'candidate_bytes': candidate.stat().st_size,
              'output_sha256': {p.name: sha256(p) for p in [raw, elf, candidate, log, attempt / 'effective-macros.txt']},
              'source_sha256': {name: sha256(source / name) for name in [
                  'Makefile', 'config.h', 'aura-raw.ld', 'rust/Cargo.lock',
                  'src/main.c', 'src/payload.c', 'src/stage1_config.c', 'src/display.c', 'src/chainload.c', 'src/nvme.c']},
              'build_command': [str(x) for x in command],
              'clang': bringup.capture([llvm / 'clang', '--version']).splitlines()[0],
              'linker': bringup.capture([llvm / 'ld.lld', '--version']).splitlines()[0], 'rust': rust_version,
              'note': 'Only builds files. Proxy allows privileged hardware access if later booted; not a read-only hardware monitor. Firmware framebuffer, USB, enrollment and recovery remain unqualified.'}
    bringup.save(attempt / 'result.json', report)
    print(json.dumps(report, indent=2))
    print('Stage-1 build review files: ' + str(attempt))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llvm-dir', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4, choices=range(1, 9))
    args = parser.parse_args()
    try:
        return build(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
