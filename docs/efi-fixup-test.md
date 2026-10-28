# Real EFI Fixup call in selected U-Boot/QEMU

This APPLY milestone passed in [CI](https://github.com/frozen-infinity/pre-asahi/actions/runs/40657157665).
The current wrapper also requires the subsequent [publication test](efi-publication-test.md);
the APPLY result remains recorded separately.

The previous test discovered the selected U-Boot's EFI DT Fixup protocol. This
step invokes its four-argument callback from an actual ARM64 EFI application.
The source pin is unchanged: `7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`.

`efi/fixup.c` first uses the existing discovery entry point, then allocates a
private pool buffer containing the tree from `efi/synthetic-test.dts` (compiled
by dtc). The first APPLY request must return BUFFER_TOO_SMALL without modifying
the input. The requested size must fit within 2 MiB. A second allocation supplies
that capacity. Zero flags, unknown flags and an invalid header must be refused;
a valid APPLY must succeed and leave a bounded FDT header. Allocated buffers are
freed before success is printed. No RESERVE or INSTALL flag is requested.

The wrapper builds only the generic `qemu_arm64_defconfig` target with explicit
nonpersistent settings. QEMU receives U-Boot and the application in memory, no
disk or network devices. It supplies the EFI byte count explicitly to bootefi.
Discovery markers alone cannot satisfy the new result gate. All negotiation,
rejection and APPLY completion markers are required, with no failure marker.
The original standalone discovery/EDK2 test remains available separately.

## What to do

Review the PR and wait for **Selected-source U-Boot EFI probe** to pass before
merging. The workflow runs automatically for relevant PR changes. No download
or hardware procedure is needed. To reproduce on an equipped Linux host:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/uboot_efi_probe.py
```

The host needs the cross-build/emulator dependencies listed in the workflow,
including clang, lld-link, dtc, aarch64-linux-gnu-gcc and qemu-system-aarch64.
Source fetch and build outputs stay under ignored `work/`. The workflow retains
our EFI application, console and hash report; it does not redistribute U-Boot.

## Evidence limits

Host tests substitute services to check allocation cleanup, oversize rejection,
input mutation and downstream failure. CI must separately run the real protocol.
Expected real result: `EMULATED_UBOOT_EFI_FIXUP_APPLY_PASS`. Until CI completes,
this is an acceptance criterion, not a reported success.

Generic QEMU does not run the Apple/J713 board hook, capture Mac firmware, launch
a kernel or establish a native entry path. No table is installed; correctness
of table publication and eventual Linux consumption remain later gates. This
step does not qualify the application for hardware use. The T7 is untouched.
