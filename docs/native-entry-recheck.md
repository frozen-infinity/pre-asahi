# Native entry recheck — 2026-10-28

The kernel-to-EFI-to-PID1 chain passed in [QEMU](https://github.com/frozen-infinity/pre-asahi/actions/runs/40664853833).
The next work is first entry on the physical J713, with an observable exit point
and a return path to macOS. Necessary Mac-side testing is authorized. This review
performed read-only queries; it did not enroll or run a custom boot object.

## Important correction: a more developed J713 downstream exists

Our earlier description of Omarchy-M4-Native as historical framebuffer research
was stale. At the reviewed
[develop commit `7d107f9`](https://github.com/Kb2uka/Omarchy-M4-Native/tree/7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3),
its [README](https://github.com/Kb2uka/Omarchy-M4-Native/blob/7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3/README.md)
reports two attended private desktop installations on Mac16,12 / J713 / T8132,
and describes experimental input, graphics and other hardware work. These are
maintainer-reported observations on their stack, not independently reproduced
results on ours. The same source distinguishes working runtime observations from
newer installer packaging that still lacks a confirmed fresh installation.

This is a substantial reuse lead. It means we should inspect and reuse relevant
J713 entry/driver work instead of assuming every missing component must be
written from scratch. It does not establish a completion estimate for pre-asahi.
The downstream kernel/module/firmware integration differs from our tested pinned
Aurora stack; no components or source pins were substituted by this review.

## What the available routes actually establish

| Source reviewed | Established scope | Remaining boundary for this project |
| --- | --- | --- |
| [Current Asahi M4 table](https://asahilinux.org/docs/platform/feature-support/m4/) | No M4 Air installer; device tree and boot framebuffer work are listed separately | The generic Asahi installer is not a verified first-entry path for J713 |
| [Asahi tethered boot](https://asahilinux.org/docs/sw/tethered-boot/) | Describes kernel development through an enrolled m1n1 environment | Our Mac has no resident Linux/m1n1 environment; USB chainloading cannot be assumed to create one |
| [Aura J700 guide at our pin](https://github.com/aurora-silicon/aura/blob/553b566f69275ff4e46ee6542a7236fb80a333a2/docs/j700-install.md) | Describes bare Stage 1 enrollment, ESP Stage 2 and per-stub Recovery authorization | J700 preparation is not J713 first-entry qualification |
| [Aura J813 guide at our pin](https://github.com/aurora-silicon/aura/blob/553b566f69275ff4e46ee6542a7236fb80a333a2/docs/j813-native-boot.md) | M5 RAM loading with an already running resident proxy and matching host ABI | Different SoC/board, and still assumes prior enrollment; do not copy its UART addresses or cold-core rules to J713 |
| [Aurora native installer at `9a16350`](https://github.com/aurora-silicon/aurora-installer/blob/9a1635086e4f1e05c08800faa29d92b1241b9f9c/macOS/README.md) | Public catalogs admit listed M1–M3 models; Neo is private developer delivery; physical qualification remains pending | A published ALARM image is not a qualified J713 installer |
| [Omarchy J713 install guide](https://github.com/Kb2uka/Omarchy-M4-Native/blob/7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3/docs/install.md) | Exact model matches; experimental macOS-launched internal-SSD installation and owner-authorized boot-policy changes | Not T7-only. Newer-host compatibility and the exact newer kit's fresh installation are not qualified by the cited trials |

The Omarchy [profile](https://github.com/Kb2uka/Omarchy-M4-Native/blob/7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3/docs/j713-installer-profile.md)
uses the Gravity installer base `6420623289fe7544cb8589b658355e57f0290fcc`
with an explicit experimental J713 profile. Its paired recovery/firmware input is
Apple's **26.5.1 / 25F80** IPSW, board **0x2c**, chip **0x8132**. That downloaded
OS-paired firmware is distinct from the currently running macOS/system firmware.
The guide's minimum-host-version check is not evidence that all later macOS
versions or all later system firmware have been tested. We did not run that
installer, its downloader, update scripts, or its expert-mode profile.

## Write and recovery consequences

The documented downstream installation can resize the internal macOS container,
create internal partitions and an OS/stub identity, collect firmware and install
boot objects, then request owner authorization in paired Recovery. Those are
material changes beyond our current read-only test. This review supplies no
partition, security-policy, installer-bypass or configure-boot commands.

The T7 can later hold test files/rootfs, but that does not create an enrolled
boot identity. [Apple's external macOS documentation](https://support.apple.com/en-ie/111336)
requires a working internal startup disk on Apple silicon. An Apple-supported
external macOS installation is also not proof that replacing its boot object
with our Aura build works. We have not established a T7-only custom-boot route.

[Apple's firmware recovery procedure](https://support.apple.com/en-us/108900)
requires another Mac with macOS 14 or later and a suitable USB data/charging
cable. Revive and restore are separate operations; restore erases the Mac.
The ability to borrow a host does not make recovery tested or guarantee that a
non-erasing revive is sufficient. A T7 data cable has not been qualified here as
a debug-UART or recovery cable. [Asahi serial-debug guidance](https://asahilinux.org/docs/hw/soc/serial-debug/)
is largely M1-specific and does not establish native J713 serial observation.

For first native work, the initial execution boundary should be a visible
Stage-1-only build/proxy observation and a demonstrated return to macOS before
adding Linux. We still need the exact expendable boot identity, authorization
procedure, output path and recovery resources reviewed together. No usable
current-macOS entry route is inferred from successful QEMU boots.

## New read-only Mac probe

`scripts/macos_boot_context.py` reads:

- model, macOS version and build;
- only chip/board numbers and OS/system bootloader strings from `/chosen`;
- whether the current root storage is internal;
- bounded external physical-device metadata, exposing only an index, size,
  transport and a T7-name match.

The helper compares bootloader IDs with the table from
[pinned Aura firmware.c](https://github.com/aurora-silicon/aura/blob/553b566f69275ff4e46ee6542a7236fb80a333a2/src/firmware.c).
Its source-derived ID list and reviewed references are in
`configs/native-entry-references.json`; a changed Aura pin requires a fresh
review. An absent match is a compatibility question, not an automatic refusal or
a reason to add an untested firmware-table entry. A match is not boot approval.

It executes only fixed `sysctl`, `sw_vers`, targeted `ioreg`, and read-only
`diskutil info/list` commands. It validates disk identifiers before queries and
never prints them, arbitrary volume/media labels, serials, UUIDs, boot arguments,
raw registry bytes or raw diagnostics. It writes no report. Query failures remain
explicitly unavailable, rather than implying no devices or a safe boot path.
Reporting indexes are never valid targets for future disk commands.

## Probe correction and validation

The original external-device parser expected a `Whole` key. macOS `diskutil info
-plist` supplies `WholeDisk`; this caused a physically listed whole disk to be
omitted with `external_storage: partial`. A failing regression reproduced that
case before the fix. The parser now uses `WholeDisk`, retaining strict support
for the legacy `Whole` fixture form. Conflicting, missing, non-boolean or false
whole-device flags remain rejected; the internal-device exclusion is unchanged.

The report now includes `external_storage_observation` with separate listed and
described counts plus allowlisted reason codes for skipped records. A failed
list query has a null listed count, not zero. Partial reports do not mean an
external disk is absent. Indexes retain their list positions even when another
record fails; they still must never be used as disk-command targets. Only the
three fixed location/whole-device boolean keys may appear in schema diagnostics;
arbitrary labels, identifiers and raw diagnostics remain excluded.

All **51** project/host tests passed locally, including a regression that failed
before this fix, conflicting-schema refusal, partial-query reporting and privacy.
The corrected probe completed all queries on the real Mac and recognized the
attached 1 TB USB T7. The private output was reviewed in chat and is not committed.
No startup or storage state was changed. CI uses substitutes and does not query a
Mac or qualify native boot.

## Your steps

Review and merge the parser-fix PR after **Native-entry probe checks** passes.
No repeat probe is currently needed: the real Mac/T7 check succeeded. For a later
read-only recheck in an updated pre-asahi clone on the Mac:

```sh
python3 scripts/macos_boot_context.py
```

Share only that filtered JSON if needed for troubleshooting. If queries are
unavailable, run from a normal local macOS Terminal without sudo; do not substitute
a full raw dump. No formatting, reboot, Recovery visit, installer download or
repeated kernel build is requested.

This closes an identification gap and records a credible downstream entry lead.
It does **not** finish first-entry qualification. Next development work remains
reviewing/adapting the exact J713 boot-identity and observable Stage-1 route for
the user's firmware and T7 preference, with concrete writes and recovery made
reviewable before any such action is requested.
