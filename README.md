# pre-asahi

An experimental, AI-assisted project aiming for native Linux support on Apple M4 devices, starting with the M4 MacBook Air and eventual Arch Linux ARM desktop support.

Independent experimental scaffold, checked 2026-10-25. This is not an installer, an official Arch/Asahi project, or a working desktop port. No hardware boot has been performed.

## First milestone

Prepare and validate pinned Asahi m1n1 + Linux artifacts and a tiny RAM-only diagnostic initramfs. The eventual hardware acceptance test is a **native** Linux kernel reaching PID 1 and printing `M4AIR_PHASE1_PID1` on a verified output channel, followed by repeatable return to macOS. A hypervisor result is useful separately, but never counts as native boot proof.

Hardware execution is blocked until the exact model/firmware and an M4-compatible, recoverable m1n1 entry and logging path have been independently verified. The public support table says installer: no. Generic Asahi installation instructions are not evidence that M4 installation works.

## How development reaches you

Changes are proposed through pull requests to [frozen-infinity/pre-asahi](https://github.com/frozen-infinity/pre-asahi). Each PR should explain what changed, what was actually tested, and the exact user steps. Hardware experiments must distinguish preparation, emulation, hypervisor execution, and native boot evidence. Early bring-up PRs remain drafts until their stated review gates are met. Merging preparation code does not mean it is safe to boot.

## Samsung T7 testing plan

Use the separate T7 for test files and, once supported, the experimental root filesystem. **There is no supported external-only M4 Air boot procedure here.** Asahi's documented initial boot setup uses internal storage, and the current M4 support table does not establish a working USB storage path. Phase 1 runs from RAM and does not need a Linux root partition on the T7. Do not erase or repartition the T7 for this milestone.

Read [the T7 plan](docs/t7-testing.md) before any hardware experiment. Current scripts never format disks, install boot components, or modify startup security. A T7 root filesystem can limit later rootfs writes to external media; it does not isolate firmware, boot policy, drivers, or hardware from experimental code.

## Intel Arch development host

Use the [Arch build-host guide](docs/arch-build-host.md) to install the cross compiler, validate AArch64 object output, and attempt a j713 kernel build. This prepares files on the Intel laptop; no T7 formatting or Mac boot changes are needed. m1n1 Rust target setup is handled separately from the distro Rust installation.

## Your steps now

From macOS Terminal, clone the development branch for this PR (after merging it, clone `main` instead):

```sh
git clone --branch phase1-scaffold-t7 https://github.com/frozen-infinity/pre-asahi.git
cd pre-asahi
python3 scripts/bringup.py identify
python3 scripts/bringup.py doctor
python3 -m unittest discover -s tests -v
```

These commands create an ordinary project folder and local reports; no administrator access is required. You can clone in an existing mounted T7 folder if desired; see the filesystem notes in the T7 plan. You can also run these preparation checks with the T7 disconnected.

Review `reports/hardware.json` and `reports/doctor.json`. Report the model/board, macOS build, missing tools, and test result in the chat. Also say whether a second development computer is available, which T7 variant/capacity you have, and whether it contains data to preserve. Do not post serial numbers, UUIDs, full disk/IORegistry dumps, or unreviewed logs. No hardware boot is requested yet.

## Local checks (writes only local project files)

Run from this directory, using Python 3.9+:

```sh
python3 scripts/bringup.py identify
python3 scripts/bringup.py doctor
python3 -m unittest discover -s tests -v
```

`identify` reads only an allowlist of macOS properties; it does not collect serial numbers, UUIDs, full IORegistry, disk layouts, or network identifiers. Inspect reports before sharing. Failures are recorded explicitly; the initial restricted development session could not read hardware sysctls, so the user's exact machine remains unconfirmed.

## Source and build workflow

```sh
# Network required. Resolves branch heads once; creates sources.lock.json.
python3 scripts/bringup.py fetch
# Re-running uses the existing exact commits, never silently updates them.
python3 scripts/bringup.py build-m1n1
# Kernel build requires a Linux build host, not macOS.
python3 scripts/bringup.py build-linux --model j713
# For the 15-inch Air choose j715 instead. Never choose a near-match DTB.
# Supply a reviewed static AArch64 BusyBox built separately:
python3 scripts/bringup.py initramfs --busybox /absolute/path/to/busybox
python3 scripts/bringup.py manifest
```

Source checkout/build code executes upstream code on the development host. Review the locked sources first. Fetch downloads Linux source (potentially large); m1n1 submodules also require network. Sources and build products live under `work/`, not on boot volumes. Fetch is idempotent and rejects mismatched remotes, commits, and dirty tracked files. Delete neither source nor lock casually: preserve failed runs as evidence. To evaluate newer upstream revisions, copy this scaffold into a new directory and resolve a new lock there.

Build prerequisites: Git, GNU make; for m1n1 see its locked README (Rust target `aarch64-unknown-none-softfloat`, LLVM/lld on macOS, dtc/ImageMagick as required). Kernel: Linux host with GCC AArch64 cross compiler, binutils, bc, bison, flex, pkg-config, OpenSSL/ELF development libraries, dtc, Python, gzip. Nothing is installed automatically. `doctor` reports tools, not a guarantee of a complete toolchain. Kernel uses arm64 defconfig plus a checked fragment; this is a diagnostic baseline, not a tuned Asahi distribution config. Review final `.config` and driver dependencies before hardware use.

There is deliberately no install, flash, partition, security-policy, or boot command. See [Phase 1](docs/phase1.md), [upstream audit](docs/upstream.md), and [test report](docs/validation.md). Artifact creation is not boot validation.

## Diagnostic userspace after the kernel and m1n1 build

Follow [the diagnostic initramfs guide](docs/diagnostic-initramfs.md) to build a hash-pinned minimal static AArch64 BusyBox, run explicit QEMU userspace checks, and package `/init`. This prepares a RAM-only diagnostic artifact; it does not provision a boot entry or prove native boot. The guide includes the exact Arch commands and validation limits.

If the BusyBox QEMU `--list` check exits 127, see [the retry steps](docs/diagnostic-initramfs.md#retry-after-the---list-check-exits-127). The minimal config now enables the listing entry point and failed smoke tests retain their error output.
