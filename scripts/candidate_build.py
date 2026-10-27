#!/usr/bin/env python3
"""Build candidate components in disposable native ARM Linux containers only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import bringup

SPEC = bringup.ROOT / 'configs/candidate-stack.json'
COMPONENTS = {'aura': ('aura', 'package'), 'kernel-config': ('linux-aurora', 'configure'),
              'kernel': ('linux-aurora', 'Image modules dtbs')}


def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def check_snapshot(root, spec):
    pins = json.loads((root / 'sources.json').read_text())
    for key, field, directory in [('kernel-aurora', 'kernel_commit', 'linux-aurora'),
                                  ('aura', 'aura_commit', 'aura')]:
        if pins[key]['commit'] != spec[field]:
            raise ValueError('Packaging/source manifest mismatch: ' + key)
        recipe = (root / 'packages' / directory / 'PKGBUILD').read_text()
        match = re.search(r'^_commit=([0-9a-f]{40})$', recipe, flags=re.M)
        if not match or match[1] != spec[field]:
            raise ValueError('Recipe/source manifest mismatch: ' + key)
    base = json.loads((root / 'images/base.json').read_text())
    if (base['sha256'] != spec['base_sha256'] or base['bytes'] != spec['base_bytes'] or
            base['signing_fingerprint'] != spec['base_signer']):
        raise ValueError('Signed base metadata changed')
    return base


def check_base_bytes(archive, base):
    if archive.stat().st_size != base['bytes'] or hash_file(archive) != base['sha256']:
        raise ValueError('Signed ALARM base size/hash mismatch; do not refresh pins automatically')


def expected_signature(status, expected):
    valid = []
    for line in status.splitlines():
        fields = line.split()
        if fields[:2] == ['[GNUPG:]', 'VALIDSIG'] and len(fields) >= 3:
            valid.append(fields[2] == expected or fields[-1] == expected)
    return bool(valid) and all(valid)


def verify_signature(archive, signature, public_key, fingerprint):
    with tempfile.TemporaryDirectory(prefix='candidate-gpg-') as name:
        args = ['gpg', '--no-options', '--homedir', name, '--batch', '--no-auto-key-retrieve']
        bringup.run(args + ['--import', public_key], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        verified = bringup.run(args + ['--status-fd', '1', '--verify', signature, archive],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not expected_signature(verified.stdout, fingerprint):
            raise ValueError('Unexpected ALARM signature signer')


def download(url, target, limit):
    if not url.startswith('https://'):
        raise ValueError('Only HTTPS source downloads are permitted')
    if target.exists():
        return
    pending = target.with_name(target.name + '.partial')
    count = 0
    with urllib.request.urlopen(url, timeout=180) as response, pending.open('wb') as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            count += len(chunk)
            if count > limit:
                raise ValueError('Download exceeds pinned size limit')
            output.write(chunk)
    pending.rename(target)


def container_args(image, recipe, entrypoint, output, component, commit):
    # No privileged mode, host device mounts, Docker socket, credentials or package installation on host.
    return ['docker', 'run', '--rm', '--platform', 'linux/arm64',
            '--security-opt', 'no-new-privileges:true', '--cap-drop', 'NET_RAW',
            '--cap-drop', 'SYS_CHROOT', '--cpus', '4', '--memory', '12g',
            '--pids-limit', '2048', '--network', 'bridge',
            '--mount', 'type=bind,src=' + str(recipe) + ',dst=/recipe-input,readonly',
            '--mount', 'type=bind,src=' + str(entrypoint) + ',dst=/candidate-entry.sh,readonly',
            '--mount', 'type=bind,src=' + str(output) + ',dst=/output',
            image, '/bin/bash', '/candidate-entry.sh', component, commit]


def build(component):
    if platform.system() != 'Linux' or platform.machine() not in ('aarch64', 'arm64'):
        raise ValueError('Run on a disposable native ARM64 Linux builder, not the Mac or Intel host')
    for tool in ['git', 'docker', 'gpg']:
        if not shutil.which(tool):
            raise ValueError('Builder lacks ' + tool)
    spec = json.loads(SPEC.read_text())
    root = bringup.WORK / 'candidate-stack'
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < 10 * 1024 ** 3:
        raise ValueError('At least 10 GiB free space is required before starting this attempt')
    attempt = Path(tempfile.mkdtemp(prefix=component + '-', dir=root))
    output = attempt / 'result'
    output.mkdir()
    bringup.save(output / 'UNQUALIFIED-BUILD-ONLY.json', {
        'status': 'NOT_FOR_INSTALLATION', 'native_boot_proven': False,
        'component': component, 'packaging_commit': spec['packaging_commit']})
    checkout = attempt / 'packaging'
    bringup.run(['git', 'init', checkout])
    bringup.run(['git', '-C', checkout, 'remote', 'add', 'origin', spec['packaging_repository']])
    bringup.run(['git', '-C', checkout, 'fetch', '--depth=1', 'origin', spec['packaging_commit']])
    bringup.run(['git', '-C', checkout, 'checkout', '--detach', spec['packaging_commit']])
    if bringup.capture(['git', '-C', checkout, 'rev-parse', 'HEAD']) != spec['packaging_commit']:
        raise ValueError('Wrong packaging revision')
    base = check_snapshot(checkout, spec)
    cache = root / 'base-cache'
    cache.mkdir(exist_ok=True)
    archive = cache / 'ArchLinuxARM-aarch64.tar.gz'
    signature = cache / 'ArchLinuxARM-aarch64.tar.gz.sig'
    download(base['url'], archive, base['bytes'])
    download(base['signature_url'], signature, 64 * 1024)
    check_base_bytes(archive, base)
    verify_signature(archive, signature, checkout / 'keys/archlinuxarm-build-system.asc', spec['base_signer'])
    package, mode = COMPONENTS[component]
    recipe = checkout / 'packages' / package
    recipe_hashes = {}
    for path in recipe.rglob('*'):
        if path.is_symlink():
            raise ValueError('Recipe symlinks require separate review')
        if path.is_file():
            recipe_hashes[str(path.relative_to(recipe))] = hash_file(path)
    receipt = {'status': 'ATTEMPT_STARTED', 'component': component, 'mode': mode,
               'packaging_commit': spec['packaging_commit'], 'kernel_commit': spec['kernel_commit'],
               'aura_commit': spec['aura_commit'], 'base_sha256': base['sha256'],
               'base_signature_signer': spec['base_signer'], 'recipe_sha256': recipe_hashes,
               'native_boot_proven': False,
               'note': 'Build-only development result. Container dependency updates are not a hermetic package snapshot.'}
    bringup.save(output / 'provenance.json', receipt)
    image = 'pre-asahi-candidate:' + attempt.name
    try:
        bringup.run(['docker', 'import', '--platform', 'linux/arm64', archive, image])
        commit = spec['aura_commit'] if component == 'aura' else spec['kernel_commit']
        args = container_args(image, recipe, bringup.ROOT / 'ci/candidate-container.sh', output, component, commit)
        print('Disposable build attempt: ' + str(attempt), flush=True)
        with (attempt / 'build.log').open('w') as log:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end='', flush=True)
            code = process.wait()
        receipt['container_exit_status'] = code
        receipt['status'] = 'BUILD_ONLY_PASSED' if code == 0 else 'BUILD_FAILED'
        receipt['output_sha256'] = {str(p.relative_to(output)): hash_file(p)
                                    for p in output.rglob('*') if p.is_file() and not p.is_symlink()
                                    and p.name != 'provenance.json'}
        bringup.save(output / 'provenance.json', receipt)
        if code:
            raise ValueError('Candidate container failed; retain build.log and provenance.json')
    finally:
        # Remove only this attempt's temporary image; never prune other builder images.
        subprocess.run(['docker', 'image', 'rm', image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('Build-only results: ' + str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=sorted(COMPONENTS), required=True)
    args = parser.parse_args()
    try:
        build(args.component)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as e:
        print('STOP: ' + str(e), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
