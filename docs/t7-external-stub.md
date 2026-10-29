# T7 first-entry proposal: no Linux partitions yet

2026-10-29. This is a source-tested **experimental proposal**, with installation
disabled. No T7 or internal partition, boot policy or selected startup OS changed.

## Actual connected-drive observation

The read-only inventory found one external whole USB T7-name/1 TB candidate,
1,000,204,886,016 bytes, currently with APFS and EFI partition categories.
That means it does not need a preliminary manual format just to prepare files.
A name/capacity match is not sufficient identity for authorizing erasure. The
helper retains neither device identifiers nor volume names and accepts no disk
target argument. Repeating it creates only console output:

```sh
python3 scripts/t7_plan.py
```

## Narrow proposed first-test layout

| Area | Intended purpose |
| --- | --- |
| GPT | Partition map created by the reviewed installer's external-disk path |
| 2,499,805,184-byte APFS stub | A separate expendable Apple OS identity, paired Recovery and proxy-only Aura boot object |
| Remaining space | Unallocated for now; no Linux rootfs or chainload partition |

My earlier APFS/FAT32/ext4 answer described possible later components too early.
They are not all required for this first loader-console test. With no filesystem
chainload or Linux payload, this profile needs neither a retained EFI partition
nor an ext4 rootfs. Kernel/initramfs can later run in RAM; future EFI/rootfs
partitioning needs its own driver and layout validation.

The external-wipe path would erase **all existing T7 data**. Do not pre-format the
drive or manually create these partitions. It must only be executed as part of a
reviewed attended installation with a freshly verified device identity. The profile
does not enable installation or contain an erasure launcher.

## What the actual installer source does

Pinned Gravity installer `6420623289fe7544cb8589b658355e57f0290fcc`, plus the
exact SHA-256-checked J713 profile patch from downstream
`7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3`, retains its expert, model, paired
firmware and SFR guards. The existing internal first-entry recipe is unchanged.
The separate `configs/t7-first-entry.json` is explicitly rehearsal-only.

The source's external disk menu admits only USB drives and filters templates
through `external_boot`. Its `action_wipe` reaches recovery preflight before
the first partition operation. The actual `DiskUtil.partitionDisk` initially
creates an EFI/free-space layout, reformats the initial partition as APFS and
grows that APFS container to the stub size. An empty OS partition list creates
no additional Linux/EFI partition and appends no filesystem target to the loader.

This is different from merely putting the loader binary on an ordinary APFS
data volume. The new OS identity still needs its files, owner data, Apple
personalization, paired Recovery and startup-policy authorization.

## Source trace and its boundaries

`ci/t7-installer-rehearsal.py` calls real pinned methods: external template
selection, firmware selection, whole-disk dispatch, partition-command generation,
OS install dispatch and boot-object construction. The disk and stub/recovery
services are fake, subprocess/network services are denied, and file writes are
confined to scratch. The Mac run used the actual reviewed Aura binary; the CI
source-dispatch run uses explicitly synthetic, non-executable payload bytes.

It checks the exact three external partition commands, synthetic preflight order,
zero Linux/ESP partition requests and the empty-variable aligned boot object.
Negative controls reject an internal synthetic target and a non-external template.
These controls belong to the rehearsal; they are not protection implemented in a
live installer. **Actual recovery preflight, stub file installation, authorization,
partitioning and native boot have not run in this trace.**

## Internal storage consequences and remaining blockers

The external-stub layout does not require shrinking the internal APFS container,
so its snapshot restriction need not be the blocker for this proposed route.
It does **not** avoid internal boot metadata. The pinned
[Recovery step](https://github.com/GravityLinux/installer/blob/6420623289fe7544cb8589b658355e57f0290fcc/src/step2/step2.sh)
has an external-volume branch copying owner-recovery data into internal
iSCPreboot. The installer also selects a new startup identity and authorizes its
custom boot object. These writes and the whole-T7 erasure need explicit review
before execution. The current macOS boot identity must never be replaced.

External startup still requires functioning internal storage, and Apple's
[external-startup guide](https://support.apple.com/en-us/111336) warns about
newer/older macOS security interactions. The guide supports ordinary external
macOS, not this custom J713 loader profile. The Asahi
[m1n1 guide](https://asahilinux.org/docs/sw/m1n1-user-guide/) requires the selected
OS's paired Recovery for registration; generic instructions do not qualify M4.

The real encrypted/decoded recovery hashes and image checksum passed earlier,
but content reads stalled after a read-only mount on this Mac. That image was
ejected and no task-created images remained attached. Do not repeat the mount
as a proven preflight. Current-host/external-stub personalization, paired Recovery
startup, visible loader output, return to macOS and recovery resources remain
unqualified. Enabling `external_boot` in a rehearsal JSON proves none of these.

## Your steps now

Review the PR and **T7 external-stub source trace**, then merge when satisfied.
Leave the T7 in its current format. No download, kernel rebuild, manual format,
snapshot deletion, installer launch or Recovery command is requested.

The proposed external route is now concrete at the source/layout level. It is
not yet a tested boot route. The next hardware-facing prerequisite is validating
the paired-recovery path and arranging a recoverable attended enrollment; the
internal container does not need to be forcibly shrunk to explore this route.
