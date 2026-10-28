from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import macos_boot_context as probe


class BootContextTests(unittest.TestCase):
    def test_chosen_allowlist_excludes_identifiers_args_and_unknown_nodes(self):
        node={'IORegistryEntryName':'chosen','chip-id':(0x8132).to_bytes(4,'little'),
              'board-id':(0x2c).to_bytes(4,'little'), 'firmware-version':b'mBoot-20457.1.29\0',
              'system-firmware-version':b'mBoot-99999.1.2\0',
              'boot-args':'PRIVATE_ARG','serial-number':'PRIVATE_SERIAL',
              'boot-uuid':'PRIVATE_UUID','IORegistryEntryChildren':[{'private':'PRIVATE_CHILD'}]}
        result=probe.chosen_fields([node],['mBoot-20457.1.29'])
        self.assertEqual(result['chip_id'],0x8132)
        self.assertTrue(result['firmware-version']['recognized_by_pinned_aura_table'])
        self.assertFalse(result['system-firmware-version']['recognized_by_pinned_aura_table'])
        self.assertNotIn('PRIVATE',json.dumps(result))
        for invalid in [[],[node,node],[{'IORegistryEntryName':'other'}]]:
            with self.assertRaises(ValueError):probe.chosen_fields(invalid,[])

    def test_invalid_values_are_not_echoed(self):
        node={'IORegistryEntryName':'chosen','firmware-version':b'PRIVATE\xff',
              'system-firmware-version':'mBoot-1.2 PRIVATE','chip-id':True,'board-id':b'12345'}
        result=probe.chosen_fields([node],[])
        self.assertIsNone(result['chip_id'])
        self.assertIsNone(result['board_id'])
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_external_device_identity_is_not_a_disk_selection(self):
        result=probe.external_summary({'Internal':False,'Whole':True,'MediaName':'Samsung PSSD T7 Media',
            'TotalSize':1000204886016,'BusProtocol':'USB','DeviceIdentifier':'disk4',
            'VolumeName':'PRIVATE_VOLUME','DiskUUID':'PRIVATE_UUID','SerialNumber':'PRIVATE_SERIAL'},1)
        self.assertTrue(result['t7_name_match'])
        self.assertEqual(result['bytes'],1000204886016)
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertNotIn('disk4',json.dumps(result))
        for bad in [{'Internal':True,'Whole':True},{'Internal':False,'Whole':False},None]:
            with self.assertRaises(ValueError):probe.external_summary(bad,1)

    def test_current_diskutil_whole_disk_key(self):
        result=probe.external_summary({'Internal':False,'WholeDisk':True,
            'MediaName':'Samsung PSSD T7 Media','TotalSize':1000204886016,'BusProtocol':'USB'},1)
        self.assertTrue(result['t7_name_match'])
        self.assertEqual(result['bytes'],1000204886016)

    def test_conflicting_or_unknown_whole_disk_flags_are_refused(self):
        for fields in [{'WholeDisk':True,'Whole':False},{'WholeDisk':'yes'},
                       {'WholeDisk':False},{}]:
            with self.assertRaises(ValueError):
                probe.external_summary(dict(Internal=False,**fields),1)

    def test_missing_queries_never_imply_qualification_or_zero_devices(self):
        result=probe.collect(lambda *a:(None,'unavailable'))
        self.assertIsNone(result['currently_running_os_boot_context'])
        self.assertIsNone(result['external_storage_observation']['listed_device_count'])
        self.assertEqual(result['query_status']['external_storage'],'unavailable')
        self.assertFalse(result['native_entry_qualified'])
        self.assertFalse(result['native_boot_proven'])
        self.assertFalse(result['disk_or_boot_state_changed'])

    def test_disk_identifier_is_validated_before_query_and_never_printed(self):
        calls=[]
        def fake(command,plist=False):
            calls.append(command)
            if command==['/usr/sbin/sysctl','-n','hw.model']:return 'Mac16,12','ok'
            if command[0]=='/usr/bin/sw_vers':return ('27.2' if command[-1]=='-productVersion' else '26B5091g'),'ok'
            if command[0]=='/usr/sbin/ioreg':return [{'IORegistryEntryName':'chosen'}],'ok'
            if command[-1]=='physical':return {'AllDisksAndPartitions':[{'DeviceIdentifier':'disk4'},
                    {'DeviceIdentifier':'disk4;PRIVATE_COMMAND'}]},'ok'
            if command[-1]=='disk4':return {'Internal':False,'Whole':True,'MediaName':'Samsung T7','TotalSize':1000000000000,'BusProtocol':'USB'},'ok'
            return {'Internal':True,'VolumeName':'PRIVATE_ROOT'},'ok'
        result=probe.collect(fake)
        self.assertEqual(len(result['external_physical_devices']),1)
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertEqual(result['query_status']['external_storage'],'unavailable')
        self.assertFalse(any('PRIVATE_COMMAND' in str(c) for c in calls))
        self.assertTrue(all(c[0] in ['/usr/sbin/ioreg','/usr/sbin/sysctl','/usr/bin/sw_vers','/usr/sbin/diskutil'] for c in calls))
        self.assertFalse(result['native_entry_qualified'])

    def test_partial_report_distinguishes_query_failure_from_absence(self):
        def fake(command,plist=False):
            if command[-1]=='physical':
                return {'AllDisksAndPartitions':[{'DeviceIdentifier':'disk4'}, {'DeviceIdentifier':'disk5'}]},'ok'
            if command[-1]=='disk4':return None,'unavailable'
            if command[-1]=='disk5':return {'Internal':False,'WholeDisk':True,
                'MediaName':'Samsung T7 PRIVATE_LABEL','TotalSize':1000000000000,'BusProtocol':'USB'},'ok'
            return None,'unavailable'
        result=probe.collect(fake)
        observation=result['external_storage_observation']
        self.assertEqual(observation['listed_device_count'],2)
        self.assertEqual(observation['described_device_count'],1)
        self.assertEqual(observation['diagnostics'],[{'external_index':1,'reason':'info_query_unavailable'}])
        self.assertEqual(result['external_physical_devices'][0]['external_index'],2)
        self.assertEqual(result['query_status']['external_storage'],'partial')
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertNotIn('disk5',json.dumps(result))
        self.assertFalse(result['native_entry_qualified'])

    def test_pin_change_stops_before_queries(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name); (root/'configs').mkdir()
            (root/'configs/native-entry-references.json').write_text(json.dumps({'aura':{'commit':'old'}}))
            (root/'configs/candidate-stack.json').write_text(json.dumps({'aura_commit':'new'}))
            with patch.object(probe,'ROOT',root):
                with self.assertRaises(ValueError):probe.collect(lambda *a:self.fail('Query must not run'))


if __name__=='__main__':unittest.main()
