from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import stage1_proxy as proxy


class Stage1ProxyContracts(unittest.TestCase):
    def test_silent_or_chainloading_profile_cannot_pass(self):
        macros='#define USE_FB\n#define NO_DISPLAY\n'
        proxy.macro_contract(macros)
        for bad in [macros.replace('NO_DISPLAY','OTHER'), macros.replace('USE_FB','OTHER')]+[
                macros+'#define '+name+'\n' for name in proxy.FORBIDDEN]:
            with self.assertRaises(ValueError):proxy.macro_contract(bad)

    def test_non_payload_boot_object_has_terminator_and_alignment(self):
        for size in [4096,65535,65536,65537]:
            raw=b'x'*(size-8)+b'STACKBOT'
            candidate=proxy.empty_boot_object(raw)
            proxy.boot_object_contract(raw,candidate)
            self.assertEqual(len(candidate)%65536,0)
            self.assertGreaterEqual(len(candidate)-len(raw),4)
            for wrong in [candidate+b'\0', raw+b'boot=UNEXPECTED\0', candidate[:-1]+b'x']:
                with self.assertRaises(ValueError):proxy.boot_object_contract(raw,wrong)

    def test_raw_image_must_be_bare_tagged_arm64_at_reviewed_entry(self):
        raw=b'##m1n1_ver##'+proxy.TAG.encode()+b'\0'
        raw=raw.ljust(4088,b'\0')+b'STACKBOT'
        elf=bytearray(64); elf[:6]=b'\x7fELF\x02\x01'
        struct.pack_into('<H',elf,18,183); struct.pack_into('<Q',elf,24,2048)
        proxy.raw_contract(raw,elf)
        for bad in [raw+b'\0',raw.replace(b'STACKBOT',b'NOTSTACK'),raw.replace(proxy.TAG.encode(),b'wrong'),
                    raw.replace(bytes(16),b'AURORA-S1-CFG01\0\0',1)]:
            with self.assertRaises(ValueError):proxy.raw_contract(bad,elf)
        struct.pack_into('<H',elf,18,62)
        with self.assertRaises(ValueError):proxy.raw_contract(raw,elf)
        struct.pack_into('<H',elf,18,183); struct.pack_into('<Q',elf,24,0)
        with self.assertRaises(ValueError):proxy.raw_contract(raw,elf)


if __name__=='__main__':unittest.main()
