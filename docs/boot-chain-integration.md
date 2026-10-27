# Next component: pinned U-Boot

Update: [U-Boot run 40493847655](https://github.com/frozen-infinity/pre-asahi/actions/runs/40493847655)
passed, and the three real component ZIPs have since passed
[the combined artifact-set review](artifact-set-review.md). The build instructions
below are retained for reproduction; no new U-Boot build is required now.

The saved kernel build is usable as an emulator-tested development input.
[Run 40468038656](https://github.com/frozen-infinity/pre-asahi/actions/runs/40468038656)
compiled the kernel, modules and Apple device trees and returned
`EMULATED_PID1_PASS` on QEMU virt/TCG. The decoded job log records:

| Evidence | Value |
| --- | --- |
| Kernel Image SHA-256 | `1a16c332d3e807e668e21b1eae1e9bc5254bf87cc4bd7f0fef0af63329c2709f` |
| Resolved config SHA-256 | `31662bde748773be1cd92ef8fb3b317a430b06c802254a75edd09c4cc636c763` |
| QEMU | 8.2.2, TCG, 16 KiB kernel, one CPU, no disks/network |
| Published artifact ZIP SHA-256 | `5d807c995fccaa776625e9acbd7034ec27be314381d232a6bcc9a559fffe19d9` |

These are CI log records; the downloaded archive has not been opened or inspected
in this chat. Keep it intact. The generic virt test did not execute Aura, U-Boot,
Apple DTBs, Mac drivers or a desktop.

## User steps after merging

1. Actions → **Candidate stack build** → **Run workflow**.
2. Select **main**, component **uboot**.
3. Share the run link here. Keep the new artifact alongside the saved kernel and
   the earlier Aura result, as separate archives.

This builds only U-Boot on a disposable ARM runner. No kernel rebuild, target
installation or T7 preparation is needed. The `kernel` mode remains available
for future source changes, and `both` still means Aura plus kernel preparation.

## Why this exact U-Boot

The same [ALARM packaging snapshot](https://github.com/aurora-silicon/alarm-aurora/blob/ac3b14d017cb5c316d21a8af3b3e38e40390b388/packages/uboot-aurora/PKGBUILD)
pins U-Boot `7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`. Its recipe builds
`apple_m1_defconfig` and packages **u-boot-nodtb.bin**. Its default generated
`u-boot.dtb` is for J274; it must not be substituted for the J713 kernel DTB.

The [pinned defconfig](https://github.com/aurora-silicon/u-boot/blob/7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c/configs/apple_m1_defconfig)
enables `CONFIG_APPLE_J713_FDT=y`. The
[board handoff](https://github.com/aurora-silicon/u-boot/blob/7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c/arch/arm/mach-apple/board.c)
calls the J713 runtime importer and RTKit helper fixups before completing the OS
DT handoff. The [J713 importer](https://github.com/aurora-silicon/u-boot/blob/7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c/arch/arm/mach-apple/j713_fdt.c)
validates source/destination identity and bounded DT buffers, imports runtime
reservations, CPU/device properties and references, and handles optional disabled
devices. This is source-level evidence of an integration contract; it is not
proof that this Mac's firmware supplies accepted runtime data.

Consequently, copying the compiled DTB into an arbitrary boot directory is not
a complete integration procedure. The earlier loader's runtime state and the
OS DT fixups must agree. USB support enabled in this configuration also does not
prove the T7 works on J713.

## What the new job checks

The existing signed-base and source/recipe-pin checks now include U-Boot. The
pinned package recipe runs unprivileged in the disposable container, with its
declared Python/ELF, swig and OpenSSL dependencies. No package is installed on
the Mac or runner host. The job produces the package and makepkg source archive,
plus the nodtb payload, ELF, resolved configuration and ELF header. It requires
a nonempty payload, AArch64 ELF and enabled J713 FDT option. Provenance includes
the exact U-Boot commit and output hashes. U-Boot does not require the pinned
Rust toolchain, so its receipt records GCC instead.

`UBOOT_PACKAGE_BUILT` is a compile/package result. The Apple binary cannot be
tested by simply replacing the kernel in the generic QEMU virt test. This job
does not assemble, enroll or execute a native boot chain.

After it passes, review the three component archives and their recorded pins
together, then define a verified loader-to-OS bundle contract before generating
an installation layout. GRUB/EFI integration, vendor firmware admission,
userspace and desktop remain further work. A recoverable entry and logging path
for the actual Mac/firmware is still required before any hardware boot.
