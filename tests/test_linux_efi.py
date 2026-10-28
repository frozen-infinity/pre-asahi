from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import linux_efi


class LinuxEFIResultTests(unittest.TestCase):
    def test_requires_real_efi_pid1_cookie_and_control_rejection(self):
        base='PRE_ASAHI_STARTING_LINUX_EFI\nEFI stub: Booting Linux Kernel\nLinux version 7.4\n[0.0] efi: EFI v2.10 by Das U-Boot\nPRE_ASAHI_LINUX_EFI_PID1_REACHED\n'
        positive=base+'PRE_ASAHI_LINUX_TREE_PUBLISHED\nPRE_ASAHI_LINUX_EFI_COOKIE=nonce\nPRE_ASAHI_LINUX_EFI_FW_BITS=64\nPRE_ASAHI_LINUX_EFI_PID1_PASS\n'
        self.assertTrue(linux_efi.outcome(positive,'nonce'))
        for missing in ['EFI stub:', 'efi: EFI v', 'Linux version ', 'PRE_ASAHI_LINUX_TREE_PUBLISHED',
                        'PRE_ASAHI_LINUX_EFI_PID1_REACHED', 'PRE_ASAHI_LINUX_EFI_FW_BITS=64']:
            self.assertFalse(linux_efi.outcome(positive.replace(missing,''),'nonce'))
        self.assertFalse(linux_efi.outcome(positive,'different'))
        self.assertFalse(linux_efi.outcome(positive+'Kernel panic','nonce'))
        self.assertFalse(linux_efi.outcome(positive+'PRE_ASAHI_LINUX_EFI_RETURNED','nonce'))
        self.assertFalse(linux_efi.outcome(positive,'nonce',True))
        control=base+'PRE_ASAHI_LINUX_CONTROL_TREE\nPRE_ASAHI_LINUX_EFI_PID1_REJECTED\n'
        self.assertTrue(linux_efi.outcome(control,'nonce',True))
        self.assertFalse(linux_efi.outcome(control,'nonce'))
        self.assertFalse(linux_efi.outcome('bootargs='+positive.replace('\n',' '),'nonce'))

    @unittest.skipUnless(shutil.which('cc'), 'Host compiler unavailable')
    def test_launcher_return_paths_restore_or_retain_live_buffer(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name)
            data=bytes.fromhex('d00dfeed00000028')+bytes(32)
            for install in [0,1]:
                (directory/'linux-test-input.h').write_text(
                    '#define TEST_INSTALL %d\n#define TEST_KERNEL_ADDRESS 0x48000000ULL\n#define TEST_KERNEL_SIZE 33016320\n' % install+
                    'static const U8 test_tree[] = {'+','.join(str(b) for b in data)+'};\n')
                binary=directory/('launcher-'+str(install))
                subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',name,
                    str(root/'tests/efi-linux-host.c'),str(root/'efi/table-consumer.c'),'-o',str(binary)],check=True)
                subprocess.run([str(binary)],check=True,timeout=10)


if __name__=='__main__':
    unittest.main()
