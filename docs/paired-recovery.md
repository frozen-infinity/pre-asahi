# Paired recovery: real Apple metadata checked before installation

Review date: 2026-10-28. The [first-stage candidate](first-native-stage.md)
cross-build passed. The next dependency is its expendable OS identity and paired
recovery, not a new kernel build. No installer or startup policy was executed.

## Actual archive result

`scripts/recovery_metadata.py` read selected ranges from the exact Apple IPSW
named in the downstream J713 profile. This ran successfully on the development
Mac, without opening device files, decoding/mounting recovery, or installing it.

| Item | Observed result |
| --- | --- |
| Apple archive | `UniversalMac_26.5.1_25F80_Restore.ipsw`, 19,769,808,058 bytes |
| Transfer | 1,518,364 bytes in 16 range requests; no full archive download |
| Manifest and SystemVersion | macOS 26.5.1, build 25F80 |
| Model | SupportedProductTypes includes Mac16,12 |
| Selected identity | J713AP, board 0x2C, chip 0x8132, macOS Customer, Erase |
| Paired recovery member | `022-21678-093.dmg.aea`, 1,140,850,688 bytes |
| Restore layout | No RestoreBundlePath key; the reviewed J713 patch supplies `restore` |

`Erase` is the identity label used by the source selector. The helper does not
perform an erase. These are archive identifiers, not private device identifiers.

The exact source selector is
[StubInstaller.load_identity](https://github.com/GravityLinux/installer/blob/6420623289fe7544cb8589b658355e57f0290fcc/src/stub.py).
The unpatched Gravity base only admits the 26.6.2 fallback for the missing restore
path; the reviewed
[J713 profile patch](https://github.com/Kb2uka/Omarchy-M4-Native/blob/7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3/patches/installer/j713-recovery-radio-profile.patch)
adds 26.5.1. Do not run the unmodified base as a J713 installer or bypass its
model checks. This helper only reproduces the metadata selection criteria; it
does not patch or launch that installer.

The bounded reader requires HTTP 206, exact Content-Range, and an unchanged
strong ETag across requests. It refuses a server's whole-file fallback, limits
network reads to 64 MiB and 100 requests, bounds decompressed metadata to 32 MiB,
rejects duplicate metadata entries, and checks ZIP CRC when reading metadata.
It records SHA-256 for the three read members. HTTPS, ETag, ZIP CRC and these
member hashes are not verification of Apple's personalization signatures or
the complete IPSW. The 26.5.1 manifest itself is 26,534,801 bytes uncompressed;
its compressed bytes are much smaller.

## Chosen direction and the remaining decision

Develop a separate minimal OS/stub identity for Stage 1, with no Linux partition
or filesystem chainload in the first observation. The first native goal is its
visible exact build tag and proxy, followed by a demonstrated return to macOS.
The later Linux RAM proof needs no T7 rootfs. Preserve the T7 for the eventual
external root filesystem once USB storage is qualified.

The reviewed installer normally allocates a roughly 2.5 GB APFS stub, and appends
OS partitions on the same chosen disk. A no-OS-partitions profile is still a
proposal. It has not been exercised through complete stub creation, Apple
personalization, ownership transfer or paired Recovery enrollment. Its write
inventory includes the new APFS container/volumes and files, security policy for
that identity, and installer-selected startup/boot metadata. If internal free
space must be created, shrinking the current macOS container is a separate
internal change. No resize is assumed or authorized by this document.

Do not substitute external macOS installation as an already qualified workaround.
[Apple's external-startup guide](https://support.apple.com/en-us/111336) says an
operational internal startup disk is required, and warns that security changes
from a newer macOS can affect significantly earlier external macOS versions.
This matters to the 27.2 host / 26.5.1 paired-firmware proposal. The installer
source also writes internal recovery authorization metadata on its external
branch, as explained in [the storage review](first-native-stage.md).

Before presenting an enrollment procedure, the next concrete technical check is
the **actual recovery payload**: bounded member retrieval, the exact encrypted
and decoded hashes from the reviewed J713 patch, native decoding, read-only
content inspection, matching recovery version and required boot/recovery assets.
That check must preserve the installer preflight order before partitioning and
must not invoke its volume-creation or step2 paths. A payload pass would still
leave newer-host compatibility, a complete stub-only profile, observation and
return/recovery unqualified. Never add a guessed current-firmware table entry.

[Apple's firmware recovery guide](https://support.apple.com/en-us/108900)
requires another Mac with macOS 14 or later. It notes that an older host may
need a software update. Revive does not erase; Restore erases the Mac. Neither
is a proven rollback for this experiment. The potential borrowed Mac remains a
recovery resource to arrange before a hardware attempt, not a reason to assume
that attempt is recoverable.

## Your steps now

Review the PR after **Apple paired-recovery metadata** passes, then merge when
satisfied. There is no new download, Recovery visit, T7 formatting, startup
setting or boot-object installation for you to perform. The check has already
run on the Mac; CI independently repeats the network metadata check.

Optional reproduction from a clean checkout on either Mac or Linux:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/recovery_metadata.py
```

The helper uses Python's standard library and writes only a local ignored report.
An existing output is refused; choose a new `--output` path for another run.
Status `APPLE_J713_RESTORE_METADATA_ONLY_PASS` does not mean recovery-image
validation, host compatibility, enrollment or native boot success. CI retains
the small report only, without distributing Apple payloads.
