#!/usr/bin/env python3
"""Prepare a review-only Stage1 kit and exercise the pinned installer on scratch files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
import bringup
import recovery_metadata as metadata
import stage1_proxy as proxy

PATCH_SHA = 'e8a9154b8ae81c5e0c4da5f39b40e10ac842cce94284d2ce02641761b7a3804b'
ARTWORK = 'e613a87e526f8fec439c4129e69dd2821b38d258'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def template_contract(profile):
    metadata.require(profile.get('installation_enabled') is False and
                     profile.get('purpose') == 'REVIEW_ONLY_FIRST_NATIVE_LOADER_ENTRY',
                     'Profile must remain review-only')
    metadata.require(len(profile.get('os_list', [])) == 1, 'Exactly one review profile required')
    template = profile['os_list'][0]
    metadata.require(template.get('partitions') == [] and template.get('external_boot') is False and
                     template.get('expert') is True and template.get('supported_fw') == ['26.5.1'] and
                     template.get('boot_object') == 'm1n1.bin' and
                     not any(k in template for k in ['package', 'next_object', 'extras', 'icon']),
                     'Profile must have no Linux/ESP/OS payload or external-boot claim')
    return template


def checked_stage1(result_path):
    result = json.loads(result_path.read_text())
    metadata.require(result.get('status') == 'STAGE1_PROXY_BUILD_ONLY_PASS' and
                     result.get('aura_commit') == proxy.PIN and result.get('build_tag') == proxy.TAG and
                     result.get('native_boot_proven') is False and
                     result.get('installed_boot_objects_changed') is False,
                     'Expected matching proxy-only build receipt')
    root = result_path.parent
    raw = root / 'source/build/aura.bin'
    elf = root / 'source/build/aura-raw.elf'
    for name, path in [('aura.bin', raw), ('aura-raw.elf', elf),
                       ('effective-macros.txt', root / 'effective-macros.txt'),
                       ('build.log', root / 'build.log')]:
        metadata.require(sha(path) == result['output_sha256'][name], 'Stage1 input changed: ' + name)
    proxy.raw_contract(raw.read_bytes(), elf.read_bytes()[:64])
    proxy.macro_contract((root / 'effective-macros.txt').read_text())
    proxy.compilation_contract((root / 'build.log').read_text())
    return raw, root / 'source'


def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, **kwargs)


def fetch_source(attempt):
    source = attempt / 'installer-source'
    run(['git', 'init', source], stdout=subprocess.DEVNULL)
    run(['git', '-C', source, 'remote', 'add', 'origin', 'https://github.com/GravityLinux/installer.git'])
    run(['git', '-C', source, 'fetch', '--depth=1', 'origin', metadata.INSTALLER])
    run(['git', '-C', source, 'checkout', '--detach', metadata.INSTALLER])
    patch = attempt / 'j713-profile.patch'
    url = ('https://raw.githubusercontent.com/Kb2uka/Omarchy-M4-Native/' + metadata.PROFILE +
           '/patches/installer/j713-recovery-radio-profile.patch')
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(1024**2 + 1)
    metadata.require(len(data) <= 1024**2 and hashlib.sha256(data).hexdigest() == PATCH_SHA,
                     'J713 profile patch changed')
    patch.write_bytes(data)
    run(['git', '-C', source, 'apply', '--check', '--unidiff-zero', patch])
    run(['git', '-C', source, 'apply', '--unidiff-zero', patch])
    run(['git', '-C', source, 'submodule', 'update', '--init', 'artwork'])
    artwork = subprocess.check_output(['git', '-C', str(source / 'artwork'), 'rev-parse', 'HEAD'], text=True).strip()
    metadata.require(artwork == ARTWORK, 'Installer artwork pin mismatch')
    environment = dict(os.environ, PYTHONPATH='src:.', PYTHONDONTWRITEBYTECODE='1')
    with (attempt / 'installer-tests.log').open('w') as log:
        run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
            cwd=source, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    return source


def rehearse(source, kit, attempt):
    # Run actual OSInstaller code, not a replacement algorithm. Any attempted
    # subprocess, network request, or diskutil operation in this boundary fails.
    command = [sys.executable, bringup.ROOT / 'ci/first-entry-rehearsal.py',
               source, kit / 'installer', attempt / 'rehearsal']
    run(command, timeout=60)
    return json.loads((attempt / 'rehearsal/result.json').read_text())


def make_kit(result_path):
    profile_path = bringup.ROOT / 'configs/first-entry.json'
    profile = json.loads(profile_path.read_text())
    template_contract(profile)
    raw, aura = checked_stage1(result_path)
    parent = bringup.WORK / 'first-entry-kit'
    parent.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=parent))
    print('First-entry kit scratch: ' + str(attempt), flush=True)
    source = fetch_source(attempt)
    kit = attempt / 'REVIEW-ONLY-first-entry-kit'
    installer = kit / 'installer'
    installer.mkdir(parents=True)
    for item in (source / 'src').iterdir():
        if item.name == 'gravity_firmware' or item.name == '__pycache__':
            continue
        if item.is_dir():
            shutil.copytree(item, installer / item.name, ignore=shutil.ignore_patterns('__pycache__'))
        elif item.is_file() and not item.name.endswith('.pyc'):
            shutil.copy2(item, installer / item.name)
    shutil.copytree(source / 'gravity_firmware', installer / 'gravity_firmware',
                    ignore=shutil.ignore_patterns('__pycache__'))
    # No ready-to-run launcher: the original main.py is supplied as reviewed source.
    (installer / 'install.sh').unlink()
    (installer / 'boot').mkdir()
    shutil.copy2(raw, installer / 'boot/m1n1.bin')
    shutil.copy2(profile_path, installer / 'installer_data.json')
    shutil.copy2(source / 'artwork/logos/icns/GravityLinux_logomark.icns', installer / 'logo.icns')
    evidence = rehearse(source, kit, attempt)
    source_dir = kit / 'source'
    source_dir.mkdir()
    for name, repo in [('aura', aura), ('installer-base', source), ('installer-artwork', source / 'artwork')]:
        with (source_dir / (name + '.tar')).open('wb') as output:
            run(['git', '-C', repo, 'archive', '--format=tar', 'HEAD'], stdout=output)
    shutil.copy2(attempt / 'j713-profile.patch', source_dir / 'j713-profile.patch')
    # Ship the actual downloaded crate sources used by this Aura build as well.
    dependencies = aura.parent / 'cargo-home/registry/src'
    metadata.require(dependencies.is_dir(), 'Missing Cargo dependency sources for binary distribution')
    with tarfile.open(source_dir / 'cargo-dependencies.tar.gz', 'w:gz') as archive:
        archive.add(dependencies, arcname='registry-src')
    own = kit / 'pre-asahi-source'
    own.mkdir()
    for name in ['scripts', 'ci', 'configs', 'docs', 'tests', '.github']:
        shutil.copytree(bringup.ROOT / name, own / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ['AGENTS.md', 'LICENSE', 'README.md', 'sources.lock.json']:
        shutil.copy2(bringup.ROOT / name, own / name)
    shutil.copy2(result_path, kit / 'stage1-build.json')
    shutil.copy2(attempt / 'installer-tests.log', kit / 'installer-tests.log')
    shutil.copy2(attempt / 'rehearsal/result.json', kit / 'rehearsal.json')
    (kit / 'READ-ME-FIRST.txt').write_text(
        'REVIEW ONLY: not qualified or enabled for installation.\n'
        'Read pre-asahi-source/docs/first-boot-attempt.md.\n'
        'This is a native-loader candidate, not a bootable USB image or Linux shell.\n'
        'No installer/Recovery commands are requested. Never replace normal macOS boot identity.\n')
    result = {'status': 'FIRST_ENTRY_KIT_BUILD_AND_SCRATCH_REHEARSAL_PASS',
              'installation_enabled': False, 'native_entry_qualified': False, 'native_boot_proven': False,
              'installer_base': metadata.INSTALLER, 'j713_patch_source': metadata.PROFILE,
              'j713_patch_sha256': PATCH_SHA, 'aura_commit': proxy.PIN,
              'rehearsal': evidence,
              'files_sha256': {str(p.relative_to(kit)): sha(p) for p in sorted(kit.rglob('*')) if p.is_file()}}
    (kit / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    output = attempt / 'REVIEW-ONLY-first-entry-kit.zip'
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(kit.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(kit))
    print(json.dumps({'status': result['status'], 'zip': str(output), 'sha256': sha(output),
                      'bytes': output.stat().st_size, 'installation_enabled': False}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage1-result', type=Path, required=True)
    args = parser.parse_args()
    make_kit(args.stage1_result.resolve())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('STOP: ' + str(error))
