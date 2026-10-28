# First boot preparation, consolidated

Review date: 2026-10-29. The user requested completing the remaining preparation
in one pass. This milestone combines the actual paired recovery image, a
distributable loader/source review kit, an empty-OS installer rehearsal, a RAM
shell, and a current storage feasibility check. It does not enroll an OS or
claim a native boot. No physical storage was formatted, resized or installed.

## What the first attempt is intended to boot

First boot the exact **Aura loader console/proxy**, with build tag
`pre-asahi-stage1-proxy-553b566f6927`. This is native loader execution, not Linux
or a Linux shell. It inherits the Apple framebuffer, keeps the console enabled,
omits filesystem chainloading, and has no appended kernel, DTB or initramfs.
The build has normal platform initialization and a privileged proxy; it is not a
read-only monitor. Compiling it does not qualify its initialization on the Mac.

Success requires visible matching tag, `Initialization complete.`,
`No valid payload found`, and `Running proxy...`, followed by a demonstrated
return to macOS through startup options. A USB host is not needed to observe
the framebuffer milestone; USB proxy transport remains a separate test.
Automatic recovery/reboot is not promised. The loader disables its watchdog.

After that succeeds, add the tested Linux kernel, correct live runtime tree
handoff, and RAM shell. The prepared initramfs enters an interactive BusyBox
shell without mounting a disk. Its proof is a diskless QEMU test that sends a
fresh command and observes the computed result, not just a boot banner. Native
USB/keyboard drivers and their firmware are not qualified by that result.
Several drivers in the saved kernel are modules, so an initramfs containing only
BusyBox cannot promise native keyboard input. It must not be installed as a
supposedly finished native shell image.

## Recovery and source provenance

The Apple archive is the exact 26.5.1 / 25F80 J713 restore profile, with
Mac16,12, chip 0x8132 and board 0x2C verified separately in its metadata.
`scripts/recovery_payload.py` stages only its 1,140,850,688-byte encrypted member,
checks its pinned SHA-256, decrypts with native macOS `aea`, checks the decoded
SHA-256, and runs `hdiutil verify`. It then attempts read-only mounting and checks
the version and required recovery tools without executing them. An attachment
failure must remain a failed inspection, even when both image hashes pass.
The scratch files are ordinary local files; they are not placed on the T7.

Hashes from the exact reviewed downstream J713 patch:

- Encrypted: `12919ca28b831ec9ff71291ac857a51cef54263f4846180c7b7311a58c51d13e`
- Decoded: `c7e05c0261a687b256c9ee58341346fbb995dfd04f03affd874524e6bc2e615d`

Source pins remain Aura `553b566f69275ff4e46ee6542a7236fb80a333a2`, Gravity
installer `6420623289fe7544cb8589b658355e57f0290fcc`, and the J713 profile patch
from Omarchy-M4-Native `7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3`.
The patch is SHA-256 checked before application; its zero-context format needs
`git apply --unidiff-zero`. The patched installer's 47 upstream tests were run on
the development Mac. Its model, expert-mode, exact firmware and SFR guards remain
intact. Passing a synthetic 27.2 firmware-selection case is not testing Apple's
personalization/enrollment on the real newer system firmware.

Upstream was rechecked on 2026-10-29. Gravity and the reviewed downstream head
were unchanged. Aura main advanced to
`ec4a6ab8b4252079e78196515577d73ef0a86135`; its intervening changes target T6041
ANS memory reservation, DAPF and NVMe handling. This J713 profile keeps its
reviewed pin. [Official Asahi M4 support](https://asahilinux.org/docs/platform/feature-support/m4/)
still lists no installer. Independent downstream experiments remain distinct.

## What the review kit actually tests

`configs/first-entry.json` has exactly one expert-only template, no OS partitions,
no package, no ESP, no next-object target, and only firmware 26.5.1. External
boot and installation remain disabled. The first-entry CI builds the real Aura
candidate, fetches the exact installer and J713 patch, and runs its upstream tests.
It then calls the actual `OSInstaller` class and boot-object builder on scratch
files. Disk/subprocess/network services are denied within that rehearsal.

The test requires zero OS partition requests, no firmware-copy/ESP requirements,
and exactly the raw image plus zero terminator/alignment bytes in `boot.bin`.
A poisoned partition request and non-expert firmware selection must reject.
This establishes those specific code paths; it does not exercise full stub file
installation, Apple personalization, security-policy authorization or boot.

The review ZIP contains the raw loader, complete installer review files,
profile, build/rehearsal receipts, corresponding Aura/installer/artwork source,
the applied patch, Cargo dependency source, and this project's preparation
source. There is no installation launcher and no Apple payload in the ZIP.
The profile's `installation_enabled: false` is an explicit review state, not a
security boundary around the original upstream source. Do not run upstream
`main.py` manually. Extraction or merging the PR does not install anything.

## Actual storage blocker

The read-only APFS limits query on this Mac reported the preferred minimum equal
to the entire current 245,107,195,904-byte container. At that observation it cannot
shrink for a new internal stub. Free space was about 31.2 GB before recovery
staging, also below the normal 38 GB reserve. Staging recovery consumes more
ordinary file space; the planner recomputes current values rather than treating
the earlier number as fixed.

The proposed stub is 2,499,805,184 bytes before GPT/alignment considerations.
There must be an actual qualified contiguous gap, or macOS must permit a suitable
shrink while retaining its normal reserve. `scripts/first_entry_plan.py` only
queries limits; it does not qualify existing free gaps or choose a disk target.
Expert mode must not silently reduce the reserve to the upstream expert-mode
1 GB. Snapshot deletion, partition deletion and forced APFS operations are not
part of this preparation. A full container minimum can arise from allocation or
snapshot/update constraints; this check does not diagnose which one applies.

The T7 remains available for files and a later Linux rootfs. An experimental
external stub would be a different, unqualified installation profile: creating
it can erase T7 data and still changes internal authorization/boot metadata.
The reviewed template does not enable it as a workaround for the internal-space
blocker. [Apple's external-startup guide](https://support.apple.com/en-us/111336)
also warns about newer/older macOS security compatibility. T7 storage alone does
not make enrollment or native firmware initialization safe.

## Enrollment and return plan, before any write is authorized

Use a **new expendable OS identity**, never the current macOS identity. The
concrete write scope would be: create its APFS stub/volumes in a qualified gap;
install exact paired-recovery/boot assets and owner data into that stub; select
that identity for startup; then let its own paired 1TR Recovery perform
owner-authenticated policy authorization and register only the checked loader.
The reviewed installer supplies the selected volume identity to its own second
step; generic copied `kmutil`/`bputil` commands are not a substitute.

This changes internal storage/metadata and per-OS startup policy. Before an
attended attempt, the actual target and write inventory must be reviewed, owner
authentication must remain local, startup options must still show normal macOS,
and recovery resources must be available. The potential borrowed recovery Mac
has not been arranged or tested. [Apple's recovery procedure](https://support.apple.com/en-us/108900)
uses another Mac with macOS 14 or later and a suitable data cable. Revive does not
erase; Restore does. Neither is a demonstrated rollback for this experiment.

For a future first attempt, observe the screen rather than issuing proxy commands.
If the exact tag/proxy milestone is reached, end that first attempt and return to
normal macOS using startup options. If it hangs, do not repeat blind attempts or
overwrite other boot objects. Recovery and forced-power-off behavior still need
the attended plan; no automatic timeout or guaranteed return is claimed.

## Your steps for this PR

Review the **First-entry kit and RAM shell** results. The two downloadable outputs
are clearly labeled review-only loader/source kit and QEMU-only shell/source.
No rebuild of the saved kernel is needed. Merge when satisfied, but do not
install either output. No T7 formatting, internal shrink, boot-policy change or
Recovery visit is requested while the storage/enrollment blockers remain.

All ordinary preparation has been grouped here. A native boot command cannot
honestly be offered as ready while these physical setup requirements remain.
The next user decision concerns a concrete storage/enrollment experiment, not
another kernel build or another synthetic DT test.
