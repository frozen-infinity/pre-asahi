from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import efi_handoff


class BoardHookBoundary(unittest.TestCase):
    def test_exact_pinned_function_suffix_is_preserved(self):
        function = 'int ft_board_setup(void *blob, struct bd_info *bd)\n{\n return 0;\n}\n'
        output = efi_handoff.board_hook('/* other board code */\n' + function)
        self.assertTrue(output.endswith(function))
        self.assertNotIn('other board code', output)

    def test_missing_or_ambiguous_function_boundary_fails(self):
        marker = 'int ft_board_setup(void *blob, struct bd_info *bd)\n'
        for source in ['unrelated', marker + '{}\n' + marker + '{}\n']:
            with self.assertRaises(ValueError):
                efi_handoff.board_hook(source)


if __name__ == '__main__':
    unittest.main()
