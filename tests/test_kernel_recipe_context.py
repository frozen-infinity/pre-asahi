from pathlib import Path
import subprocess
import tempfile
import unittest


class KernelRecipeContext(unittest.TestCase):
    def test_real_build_invocation_uses_makepkg_source_directory(self):
        entrypoint = (Path(__file__).resolve().parents[1] / 'ci/candidate-container.sh').read_text()
        invocation = entrypoint.split("<<'KERNEL_BUILD'\n", 1)[1].split('\nKERNEL_BUILD', 1)[0]
        with tempfile.TemporaryDirectory(prefix='recipe with spaces ') as name:
            recipe = Path(name)
            (recipe / 'src/linux').mkdir(parents=True)
            (recipe / 'PKGBUILD').write_text('''
_srcname=linux
build() {
    cd "$_srcname"
    test "$PWD" = "$srcdir/linux"
    printf 'BUILD_FROM_SOURCE_OK\\n'
}
package() { echo 'must not package' >&2; return 99; }
''')
            completed = subprocess.run(['bash', '-euo', 'pipefail'], input=invocation,
                                       cwd=recipe, text=True, capture_output=True, check=True)
            self.assertEqual(completed.stdout, 'BUILD_FROM_SOURCE_OK\n')


if __name__ == '__main__':
    unittest.main()
