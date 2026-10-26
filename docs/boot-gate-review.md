# Boot-entry review — 2026-10-26

Status: **artifact preparation reported successful; native hardware boot remains blocked by an unverified entry/firmware/logging path.** This is not a request to provision or bypass anything.

## Evidence so far

The user reported successful Intel Arch cross-builds of the pinned Linux j713 Image/DTB and m1n1. The DTB lists apple,j713 and apple,t8132. BusyBox static ELF and QEMU applet/shell checks passed; the cpio listing contains executable init and BusyBox, expected directories and dev/console (character 5,1). The initramfs is approximately 478 KiB compressed. Artifact hashes and source lock have been retained in the user's local manifest. No native PID 1 log, hardware boot or T7 rootfs test has been reported. We have not independently reproduced the user's builds or inspected their binary files.

The build/packaging portion of Phase 1 is complete on the evidence provided; the first-boot proof portion is not. Avoid further source/compiler changes unless a specific unresolved check requires them.

## Upstream findings

- [Asahi M4 support](https://asahilinux.org/docs/platform/feature-support/m4/) still lists no installer for the M4 Air. Linux device-tree support and a boot framebuffer do not establish an end-to-end entry route or usable desktop.
- [Installer src/main.py at e93743d52178b3e26e428fa05174ef549abf30cb](https://github.com/AsahiLinux/asahi-installer/blob/e93743d52178b3e26e428fa05174ef549abf30cb/src/main.py): j713ap is absent from DEVICES. The device check rejects absent chip/model entries. Do not add a model entry, enable expert mode or change a check just to force this machine through installation. The installer revision was inspected read-only; it was not run.
- [m1n1 firmware.c at the user's pinned revision](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/src/firmware.c): detect_firmware matches exact bootloader identifier strings. Its table includes 27.0 / mBoot-20457.1.29; no explicit 27.2 entry was found. An unmatched string is recorded as unknown. This is a compatibility question, not proof that 27.2 cannot boot: installed macOS, per-OS boot firmware and system firmware must not be conflated. No downgrade or firmware-table patch is proposed.
- [Generic tethered boot guidance](https://asahilinux.org/docs/sw/tethered-boot/) assumes an established m1n1 environment. Its installation and recovery instructions are not evidence that M4 Air provisioning works. A second Intel host is available, but the cable/port and actual target transport have not been verified.
- [Pinned proxyclient/m1n1/setup.py](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/proxyclient/m1n1/setup.py) is not an inert identification script: importing it connects to a target and resets a panic counter. Do not run proxy tooling merely to see whether something happens.

## Next information, read-only

The helper has now run successfully in the connected macOS environment and reported the expected Mac16,12/M4 model. The allowlisted firmware output was reviewed in the chat, not committed. There is no need to repeat the command unless identifying a different machine or a later firmware state. The remaining user question is whether an Asahi/m1n1 boot entry already exists.

On the Mac's existing pre-asahi clone, retain any local changes before changing branches:

```sh
git fetch origin
git switch --track origin/boot-gate-review
python3 scripts/macos_firmware.py
```

If this branch already exists locally, use `git switch boot-gate-review`. This helper queries system_profiler's hardware report in memory, prints only model/chip and firmware/OS-loader fields, and discards serial numbers, UUIDs and unknown fields. It does not write a report or invoke diskutil, boot selection, recovery, security-policy or proxy commands. Some fields may say "not reported"; do not substitute a full unfiltered hardware report.

Send that filtered output in the chat. Also state whether the Mac has an existing Asahi/m1n1 boot entry, or has only run macOS. Do not run an installer to answer this. If unsure, say so; there is no need to change startup selection or boot into recovery for this step.

## Remaining gates

1. Identify actual system/OS boot firmware as far as safely available. The filtered report is a clue and does not by itself expose every boot-policy/firmware detail.
2. Establish a documented M4 Air entry procedure for that firmware, including what internal storage/security changes it needs and a specific return-to-macOS/recovery procedure. No supported procedure was established by this review. If absent, the task becomes upstream boot/provisioning development, not repeated artifact builds or T7 preparation.
3. Establish native-mode observability and exact launch arguments independently of a hypervisor-only success. The DT stdout alias or a cable connector alone is insufficient. Audit the actual proxy tools for side effects before invoking them.
4. Verify userspace ELF segment compatibility with the 16 KiB kernel, final kernel config, and payload layout before any reviewed launch. QEMU user-mode success is useful but does not validate all 16 KiB kernel loading constraints.
5. Only after those gates prepare a separate concrete hardware test proposal. Keep the T7 unchanged: external storage cannot replace the missing initial entry route, and USB/T7 support is still unverified.

Do not install the current artifacts, concatenate a purported boot image, alter startup security, manually configure-boot, bypass model checks, or erase storage based on build success. Native acceptance still requires the full kernel-to-PID1 transcript plus repeatable macOS recovery.

## Validation

Inspected the pinned m1n1 firmware logic/setup module, a recorded installer revision and current upstream docs. The firmware helper's privacy filtering and missing-record behavior are unit tested; the helper also ran successfully in the connected macOS environment, printing only allowlisted fields. No raw hardware report was saved. All seven scaffold tests passed locally. No hardware experiment or persistent target change was performed in this review.
