import copy
import io
from pathlib import Path
import plistlib
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import recovery_metadata as recovery


def manifest():
    return {'ProductVersion': '26.5.1', 'ProductBuildVersion': '25F80',
            'SupportedProductTypes': ['Mac16,12'], 'BuildIdentities': [{
                'ApBoardID': '0x2C', 'ApChipID': '0x8132',
                'Info': {'DeviceClass': 'j713ap', 'RestoreBehavior': 'Erase',
                         'Variant': 'macOS Customer', 'BuildNumber': '25F80'},
                'Manifest': {'BaseSystem': {'Info': {'Path': recovery.RECOVERY}}}}]}


class Response(io.BytesIO):
    def __init__(self, data=b'', status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {'Content-Length': '2000', 'ETag': '"fixture"'}

    def geturl(self):
        return recovery.URL


class MetadataContracts(unittest.TestCase):
    def test_exact_identity_required_without_converting_it_to_boot_approval(self):
        original = manifest()
        recovery.identity_contract(original)
        for key, value in [('ApBoardID', '0x2D'), ('ApChipID', '0x8133')]:
            changed = copy.deepcopy(original)
            changed['BuildIdentities'][0][key] = value
            with self.assertRaises(ValueError):
                recovery.identity_contract(changed)
        for field, value in [('DeviceClass', 'j715ap'), ('RestoreBehavior', 'Update'),
                             ('Variant', 'macOS Customer Software Update'), ('BuildNumber', '25G83')]:
            changed = copy.deepcopy(original)
            changed['BuildIdentities'][0]['Info'][field] = value
            with self.assertRaises(ValueError):
                recovery.identity_contract(changed)
        changed = copy.deepcopy(original)
        changed['BuildIdentities'] *= 2
        with self.assertRaises(ValueError):
            recovery.identity_contract(changed)

    def test_untrusted_range_response_never_falls_back_to_whole_download(self):
        for status, headers, payload in [
            (200, {}, b'abc'),
            (206, {'Content-Range': 'bytes 0-2/2001', 'ETag': '"fixture"'}, b'abc'),
            (206, {'Content-Range': 'bytes 0-2/2000', 'ETag': '"changed"'}, b'abc'),
            (206, {'Content-Range': 'bytes 0-2/2000', 'ETag': '"fixture"'}, b'ab'),
            (206, {'Content-Range': 'bytes 0-2/2000', 'ETag': '"fixture"'}, b'abcd')]:
            def opener(request, timeout):
                return Response() if request.get_method() == 'HEAD' else Response(payload, status, headers)
            with self.subTest(status=status, headers=headers, size=len(payload)):
                source = recovery.RangeArchive(opener)
                with self.assertRaises(ValueError):
                    source.read(3)

    def test_range_budget_is_checked_before_request(self):
        calls = []
        def opener(request, timeout):
            calls.append(request)
            return Response()
        source = recovery.RangeArchive(opener)
        source.transferred = recovery.LIMIT - 2
        with self.assertRaises(ValueError):
            source.read(3)
        self.assertEqual(len(calls), 1)

    def test_successful_range_has_exact_entity_and_bounds(self):
        def opener(request, timeout):
            if request.get_method() == 'HEAD':
                return Response()
            self.assertEqual(request.get_header('Range'), 'bytes=100-102')
            self.assertEqual(request.get_header('If-match'), '"fixture"')
            return Response(b'abc', 206, {'Content-Range': 'bytes 100-102/2000', 'ETag': '"fixture"'})
        source = recovery.RangeArchive(opener)
        source.seek(100)
        self.assertEqual(source.read(3), b'abc')
        self.assertEqual((source.tell(), source.transferred), (103, 3))

    def test_duplicate_and_oversized_metadata_are_rejected(self):
        from unittest.mock import Mock
        archive = Mock()
        info = zipfile.ZipInfo('BuildManifest.plist')
        info.file_size = 33 * 1024**2
        info.compress_size = 1
        archive.infolist.return_value = [info]
        with self.assertRaises(ValueError):
            recovery.read_member(archive, info.filename)
        info.file_size = 1
        archive.infolist.return_value = [info, info]
        with self.assertRaises(ValueError):
            recovery.read_member(archive, info.filename)
        archive.open.assert_not_called()

    def test_metadata_pass_never_means_recovery_or_hardware_pass(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, data in [('BuildManifest.plist', manifest()),
                               ('SystemVersion.plist', {'ProductVersion': '26.5.1', 'ProductBuildVersion': '25F80'}),
                               ('usr/standalone/bootcaches.plist', {'bless2': {}})]:
                archive.writestr(name, plistlib.dumps(data))
            archive.writestr(recovery.RECOVERY, b'synthetic, not a recovery image')
        stream.seek(0)
        result = recovery.inspect(stream)
        for key in ['recovery_payload_hash_verified', 'recovery_decoded_or_mounted',
                    'host_compatibility_qualified', 'native_entry_qualified',
                    'native_boot_proven', 'disk_or_boot_state_changed']:
            self.assertIs(result[key], False)


if __name__ == '__main__':
    unittest.main()
