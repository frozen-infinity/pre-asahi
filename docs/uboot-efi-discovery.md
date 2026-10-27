# Real EFI discovery in selected-source U-Boot

The next test builds U-Boot commit
`7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`, the same revision as the saved Apple
package, using its **qemu_arm64_defconfig**. This is a separate generic-board
test build. The saved Apple binary cannot run on QEMU virt and is not modified.
The J713 board hook, hardware helper and Aura are not executed by this test.

Unlike EDK2, this U-Boot build is configured to provide the selected revision's
real EFI DT-fixup protocol. The unchanged standalone EFI application then runs
through U-Boot's actual EFI services and looks up that protocol. It still does
not call Fixup or start Linux. This separates protocol discovery/ABI evidence
from the earlier synthetic J713 importer and mocked board-hook tests.

## Build and execution

The helper runs on disposable Linux builders with GCC's AArch64 cross compiler,
clang/LLD for the EFI app, and QEMU. It shallow-fetches the exact U-Boot commit,
verifies HEAD, starts from qemu_arm64_defconfig and applies an explicit test-only
overlay:

* EFI loader, binary `bootefi` command and DT-fixup protocol enabled.
* Autoboot disabled so the harness controls the single test command.
* U-Boot environment/EFI variable storage set to nonpersistent implementations.
* Network and Apple board profiles excluded.

Required settings are checked after olddefconfig. This profile is never used for
the saved Apple artifacts and is not an installation configuration.

QEMU executes U-Boot as its generic ARM64 firmware with TCG and 1 GiB RAM. The
EFI image is preloaded into virtual RAM at `0x44000000`; the helper waits for the
U-Boot prompt and sends `bootefi 0x44000000` to the emulated serial console.
There is no disk image, ESP, pflash backing file, physical disk/USB passthrough
or network. No command is sent to a host terminal or the Mac's bootloader.

Acceptance requires the U-Boot banner and all three guest markers:

```text
PRE_ASAHI_EFI_PROBE_STARTED
PRE_ASAHI_DT_FIXUP_AVAILABLE
PRE_ASAHI_NO_LINUX_LAUNCH
```

Missing/unsupported/error protocol markers cannot pass. The console is capped
and execution times out after 90 seconds; QEMU is terminated after observation.
Reports record the commit, resolved configuration and firmware/probe/console
hashes, tool versions and explicit false native/Apple/helper/Fixup/Linux flags.

## User steps and validation

The PR automatically runs **Selected-source U-Boot EFI probe** when its test
workflow, helper or EFI app changes. Review that check rather than starting
another build. If a manual reproduction is needed after merge, open
**Actions → Selected-source U-Boot EFI probe → Run workflow → main**.
No kernel rebuild or Mac/T7 action is required.

Local validation covers 37 project tests, including evidence rejection and
profile checks, plus workflow YAML parsing. The actual Linux cross-build and
emulation verdict is supplied by the matching CI check; local macOS does not
have the GNU cross-build prerequisites and the Docker daemon is not running.
The helper refuses to start that cross-build on macOS.

The workflow retains the console, runner log, configuration, report and this
project's EFI executable. It does not publish a QEMU U-Boot binary as an Apple
boot artifact. Upstream source and build trees stay ignored; source pins are
unchanged. Compiler/build dependencies come from the runner's package repository,
so this is not a hermetic toolchain snapshot.

## Meaning of a pass

`EMULATED_UBOOT_EFI_PROTOCOL_PRESENT` establishes that the selected U-Boot source,
under this generic QEMU configuration, loads our actual arm64 EFI app and exposes
the expected protocol/revision. It does not establish that the Apple configuration
starts on the M4, accepts the live firmware state, or boots Linux. Invoking Fixup
with a selected OS tree is a subsequent caller implementation step. Native entry,
logging and recovery remain separate model/firmware-specific requirements.
