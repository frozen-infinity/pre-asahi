# Full-system test of the existing 16 KiB kernel and diagnostic initramfs

The Mac has no existing m1n1 boot environment. A supported first-provisioning route for its current model/firmware has not been established. This is an independent test on the Intel Arch laptop to exercise Linux loading the static BusyBox and running /init with the existing 16 KiB kernel. It is not an M4 hardware test, an m1n1 hypervisor run, or an Arch rootfs installation.

Unlike the earlier QEMU user-mode smoke test, this boots an entire kernel on QEMU's generic ARM `virt` machine. It uses exactly the existing uncompressed Image and initramfs.cpio.gz without rebuilding them. QEMU generates its own device tree; the Apple j713 DTB and m1n1 are deliberately not used. See [QEMU virt documentation](https://www.qemu.org/docs/master/system/arm/virt.html) and the [AArch64 Image header specification](https://docs.kernel.org/arch/arm64/booting.html).

## User steps — Arch laptop only

Keep the Mac and T7 disconnected. Inside your existing pre-asahi clone, inspect git status and preserve any local changes before switching:

```sh
git fetch origin
git switch --track origin/qemu-kernel-check
sudo pacman -Syu --needed qemu-system-aarch64
python3 -m unittest discover -s tests -v
python3 scripts/qemu_kernel.py
```

If the branch already exists locally, use `git switch qemu-kernel-check`. [qemu-system-aarch64 is an official Arch package](https://archlinux.org/packages/extra/x86_64/qemu-system-aarch64/). Review its normal full-upgrade transaction. No other package/toolchain changes, source-lock updates, source downloads or kernel/BusyBox rebuilds are required. The helper uses only Python's standard library and the existing bringup helpers. Run it without sudo.

## How acceptance works

Before starting QEMU, the helper checks the uncompressed AArch64 Image magic and page-size flags (16 KiB, little endian) and verifies built-in PL011 console/initramfs prerequisites in the existing .config. A missing prerequisite is reported as a stop; do not change the established M4 kernel configuration blindly.

The guest uses TCG software emulation, one max-model CPU, 1 GiB RAM, a serial console, no default devices, no network and no attached disk. There is no host device passthrough or shared filesystem. Only Image and the compressed initramfs are loaded into guest RAM. /init therefore runs inside the guest kernel, not on the build host. Its mounts operate on guest pseudo-filesystems.

The script records a console.log and result.json in a new `reports/qemu-virt-*` directory for every attempt. Success requires a Linux banner, QEMU virt identification and the exact standalone M4AIR_PHASE1_PID1 line with no kernel panic, followed by two seconds of observation. A command-line echo of the marker does not pass. The acceptance marker is the existing diagnostic /init marker; its interpretation is always tied to the recorded emulated platform.

Status is `EMULATED_PID1_PASS`; native_boot_proven and m1n1_tested remain false. The emulator is then terminated deliberately, so a termination signal exit code in the JSON is expected after success. This is a short loading/PID1 check, not a stability, suspend or hardware test. The default timeout is 180 seconds; on a slow laptop you can retry with `python3 scripts/qemu_kernel.py --timeout 300` after reviewing the retained log. Every run uses a new log directory so a stale success cannot be consumed.

Send the printed result.json and the last console lines around the PID 1 marker. The result includes the exact QEMU command/version and SHA-256 hashes of Image, initramfs, config, source lock and console transcript. It does not change reports/manifest.json. Check any local paths before posting. On failure send the first meaningful guest/QEMU error, not only the final status.

## What remains blocked after success

A pass establishes that this kernel/userspace combination reaches PID 1 on an emulated platform with 16 KiB pages. It does not exercise the Apple device tree, m1n1, Apple firmware, USB/T7, hardware output transport or recovery. The [boot-entry review](boot-gate-review.md) remains in force. The official [M4 feature status](https://asahilinux.org/docs/platform/feature-support/m4/) still lists no installer; no verified first-entry route was found during this check. Do not run generic installer/recovery commands, bypass supported-model checks, downgrade firmware or erase the T7 based on an emulated pass.

The next native bring-up work must establish a model/firmware-specific provisioning design, including any necessary internal boot components, observability and recovery, before preparing a concrete hardware procedure. Further artifact builds alone cannot solve that problem. No change to the target Mac is proposed by this PR.

## Validation

Nine local Python tests passed, including rejecting non-16-KiB Image headers, marker-only/command-line false positives and panic logs. CLI help and documented Bash syntax passed. The QEMU launch options were checked locally without boot artifacts; the user's actual Image/initramfs are not available in this workspace, so no full-system PID 1 pass is claimed here. Actual execution remains to be performed on the Arch host. These tests do not emulate M4 hardware.
