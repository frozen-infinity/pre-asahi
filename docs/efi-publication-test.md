# EFI device-tree publication and consumer check

The APPLY-only milestone passed in [PR #23's CI run](https://github.com/frozen-infinity/pre-asahi/actions/runs/40657157665).
This next check tests the configuration-table step that a future EFI Linux
handoff would need. It remains a generic ARM64 QEMU test.

## What runs

The unchanged selected U-Boot source pin is
`7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`. The runner builds its generic QEMU
profile once, then runs two EFI applications in fresh QEMU instances:

1. The previous APPLY-only app must still pass negotiation and rejection checks.
2. `publication.c` saves the existing FDT table pointer (or its absence), sizes a
   private synthetic DTB, then requests APPLY | INSTALL through the real Fixup
   protocol. It never requests RESERVE.
3. A separately compiled consumer reads only the EFI system table. It locates the
   standard FDT GUID, rejects ambiguous table entries, walks bounded FDT structure
   and string blocks, and requires the synthetic root cookie. It is a function
   in the same EFI executable, not a second loaded image or Linux EFI stub.
4. The app restores the previous table using InstallConfigurationTable and checks
   the result before freeing its private buffers. It re-reads the current system
   table after EFI operations rather than caching its array pointer.

The FDT GUID matches [the selected source's efi_api.h](https://github.com/aurora-silicon/u-boot/blob/7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c/include/efi_api.h).
Shared EFI ABI offsets are asserted at compilation, and all project C/header
inputs plus the source/compiled synthetic fixture are hashed in build reports.

If restoration fails and the buffer may still be published, the app fails and
retains that buffer until QEMU teardown. It must never free a live published
pointer. Host substitute-service tests cover this case, both original-table
states, partial publication on failure, corrupt content, oversize requests,
missing/duplicate tables and allocation lifetime. They do not prove real EFI
behavior; the QEMU run is a separate required check.

## Acceptance and user steps

Review and merge only after **Selected-source U-Boot EFI probe** passes. It runs
automatically for this PR. No download, Mac startup change or T7 preparation is
needed. On an equipped Linux cross-build host, optionally reproduce with:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/uboot_efi_probe.py
```

The overall result must be `EMULATED_UBOOT_EFI_PUBLICATION_PASS`. APPLY alone is
insufficient: publication, consumer, restoration and final pass markers are all
required, with no failure/retained-buffer marker. Separate consoles, both EFI
apps, configuration and hash reports are retained for seven days. Upstream
U-Boot binaries are not redistributed by this workflow.

## Limits and next gate

This validates temporary publication and content consumption in one EFI app,
using a trusted firmware table pointer and synthetic data. The small consumer is
a test reader, not a general-purpose validator for arbitrary untrusted pointers.
It does not test a loaded Linux EFI stub, ExitBootServices, J713 firmware fixups,
native boot or restoration after firmware reset. No disk or network device is
attached to QEMU. The next integration gate is a genuine Linux EFI consumer;
M4 entry/logging/recovery verification remains necessary before native execution.
