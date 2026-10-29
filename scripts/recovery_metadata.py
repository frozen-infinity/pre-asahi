#!/usr/bin/env python3
"""Inspect bounded metadata ranges from the pinned Apple IPSW; never install it."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import plistlib
import re
import urllib.request
import zipfile

URL = ('https://updates.cdn-apple.com/2026SpringFCS/fullrestores/122-88870/'
       'E47EBB85-45F2-4E3C-B9E7-6FF7868C2FBA/UniversalMac_26.5.1_25F80_Restore.ipsw')
INSTALLER = '6420623289fe7544cb8589b658355e57f0290fcc'
PROFILE = '7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3'
RECOVERY = '022-21678-093.dmg.aea'
LIMIT = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


class RangeArchive(io.RawIOBase):
    """No whole-file fallback; bind requests to one strong HTTP entity tag."""
    def __init__(self, opener=urllib.request.urlopen, transfer_limit=LIMIT, request_limit=100):
        self.opener = opener
        require(0 < transfer_limit <= 2 * 1024**3 and 0 < request_limit <= 1024,
                'Invalid bounded transfer limits')
        self.transfer_limit = transfer_limit
        self.request_limit = request_limit
        self.position = 0
        self.transferred = 0
        self.requests = 0
        with opener(urllib.request.Request(URL, method='HEAD'), timeout=30) as response:
            require(response.status == 200 and response.geturl() == URL,
                    'Unexpected archive HEAD response or redirect')
            self.size = int(response.headers['Content-Length'])
            self.etag = response.headers.get('ETag', '')
        require(1024 < self.size < 64 * 1024**3, 'Unexpected archive size')
        require(re.fullmatch(r'"[^"\r\n]+"', self.etag), 'Missing strong archive ETag')

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        require(whence in (0, 1, 2) and 0 <= position <= self.size, 'Invalid ZIP seek')
        self.position = position
        return position

    def read(self, size=-1):
        size = self.size - self.position if size < 0 else min(size, self.size - self.position)
        require(size <= self.transfer_limit - self.transferred and self.requests < self.request_limit,
                'Metadata transfer budget exceeded')
        if not size:
            return b''
        start, end = self.position, self.position + size - 1
        request = urllib.request.Request(URL, headers={
            'Range': f'bytes={start}-{end}', 'If-Match': self.etag,
            'Accept-Encoding': 'identity'})
        self.requests += 1
        with self.opener(request, timeout=30) as response:
            require(response.status == 206 and response.geturl() == URL,
                    'Server refused bounded range or redirected')
            require(response.headers.get('Content-Range') == f'bytes {start}-{end}/{self.size}',
                    'Incorrect Content-Range')
            require(response.headers.get('ETag') == self.etag, 'Archive entity changed')
            require(response.headers.get('Content-Encoding', 'identity') == 'identity',
                    'Unexpected HTTP content encoding')
            data = response.read(size + 1)
        require(len(data) == size, 'Truncated or oversized archive range')
        self.transferred += len(data)
        self.position += len(data)
        return data


def read_member(archive, name):
    matches = [item for item in archive.infolist() if item.filename == name]
    require(len(matches) == 1, 'Missing or duplicate metadata member: ' + name)
    info = matches[0]
    require(0 < info.file_size <= 32 * 1024**2 and info.compress_size <= 16 * 1024**2,
            'Metadata member exceeds size limit')
    with archive.open(info) as source:
        data = source.read(32 * 1024**2 + 1)
    require(len(data) == info.file_size, 'Metadata length mismatch')
    return data


def identity_contract(manifest):
    require(manifest.get('ProductVersion') == '26.5.1' and
            manifest.get('ProductBuildVersion') == '25F80', 'Wrong restore version/build')
    require('Mac16,12' in manifest.get('SupportedProductTypes', []), 'Missing Mac16,12')
    identities = [i for i in manifest['BuildIdentities']
                  if i.get('ApBoardID') == '0x2C' and i.get('ApChipID') == '0x8132'
                  and i.get('Info', {}).get('DeviceClass') == 'j713ap'
                  and i['Info'].get('RestoreBehavior') == 'Erase'
                  and i['Info'].get('Variant') == 'macOS Customer']
    require(len(identities) == 1, 'Missing or ambiguous J713 customer erase identity')
    identity = identities[0]
    require(identity['Info'].get('BuildNumber') == '25F80', 'Wrong identity build')
    require(identity['Manifest']['BaseSystem']['Info']['Path'] == RECOVERY,
            'Unexpected paired recovery member')
    return identity


def inspect(source):
    hashes = {}
    with zipfile.ZipFile(source) as archive:
        data = read_member(archive, 'BuildManifest.plist')
        identity_contract(plistlib.loads(data))
        hashes['BuildManifest.plist'] = hashlib.sha256(data).hexdigest()
        data = read_member(archive, 'SystemVersion.plist')
        version = plistlib.loads(data)
        require(version.get('ProductVersion') == '26.5.1' and
                version.get('ProductBuildVersion') == '25F80', 'SystemVersion mismatch')
        hashes['SystemVersion.plist'] = hashlib.sha256(data).hexdigest()
        data = read_member(archive, 'usr/standalone/bootcaches.plist')
        bootcaches = plistlib.loads(data)
        require(isinstance(bootcaches.get('bless2'), dict), 'Missing bless2 layout')
        restore = bootcaches['bless2'].get('RestoreBundlePath', 'restore')
        require(restore == 'restore', 'Unexpected restore bundle path')
        hashes['usr/standalone/bootcaches.plist'] = hashlib.sha256(data).hexdigest()
        recovery = [i for i in archive.infolist() if i.filename == RECOVERY]
        require(len(recovery) == 1 and recovery[0].file_size > 0, 'Missing recovery payload')
        return {'status': 'APPLE_J713_RESTORE_METADATA_ONLY_PASS',
                'installer_base': INSTALLER, 'downstream_profile': PROFILE,
                'version': '26.5.1', 'build': '25F80', 'model': 'Mac16,12',
                'device_class': 'j713ap', 'board_id': '0x2C', 'chip_id': '0x8132',
                'restore_bundle_path': restore,
                'restore_bundle_fallback_required': 'RestoreBundlePath' not in bootcaches['bless2'],
                'metadata_sha256': hashes,
                'recovery_member': RECOVERY, 'recovery_bytes': recovery[0].file_size,
                'recovery_payload_downloaded': False, 'recovery_payload_hash_verified': False,
                'recovery_decoded_or_mounted': False, 'host_compatibility_qualified': False,
                'native_entry_qualified': False, 'native_boot_proven': False,
                'disk_or_boot_state_changed': False,
                'note': 'Archive identity metadata only, not recovery validation or boot approval. '
                        'Erase is the upstream identity selector, never an action performed here.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('reports/recovery-metadata.json'))
    args = parser.parse_args()
    # Exclusive output creation prevents overwriting a saved result or following a symlink.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    require(not args.output.exists() and not args.output.is_symlink(), 'Output already exists')
    with RangeArchive() as source:
        result = inspect(source)
        result.update(archive_url=URL, archive_bytes=source.size, archive_etag=source.etag,
                      metadata_transfer_bytes=source.transferred, range_requests=source.requests)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        raise SystemExit('STOP: ' + str(error))
