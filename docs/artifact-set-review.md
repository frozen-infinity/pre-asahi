# Verify the saved component archives together

The three successful CI runs are now pinned by artifact ID, ZIP byte count and
GitHub-reported SHA-256 in `configs/artifact-set.json`. The checker reads those
ZIPs without extracting files, installing packages or executing their contents.
It works with Python 3.9+ on macOS or Linux; no emulator or rebuild is required.

## Completed local verification

The actual downloaded U-Boot ZIP and the complete `UNQUALIFIED-candidate-kernel-3.zip`
in Downloads were read, together with Aura downloaded through the GitHub
connector. All three ZIP hashes matched their selected CI artifacts. The earlier
kernel ZIPs without `-3` or ending `-1`/`-2` were incomplete; they were not modified.

The checker verified all **145 recorded build outputs**, matching source pins,
Aura Stage 1 ARM64 Mach-O and nonempty raw/Stage 2 payloads, static AArch64 U-Boot
ELF and enabled J713 FDT configuration, and identical packaged/standalone nodtb
payloads. It checked the 16 KiB Image header, Rust/page-size configuration, J713
DTB header and trusted artifact hash, QEMU input hashes, saved console hash and
actual PID 1 acceptance marker. It does not implement a full semantic DT parser.

The kernel DTB hash was
`95e6f0334a39f19af240c95a1678b43c34d5800bbd42263311f6ba540dd29dca`,
matching the earlier independently compiled candidate DTB. The exact Image hash
was `1a16c332d3e807e668e21b1eae1e9bc5254bf87cc4bd7f0fef0af63329c2709f`.

Result: **PINNED_ARTIFACT_SET_VERIFIED_NOT_BOOTABLE**.

This is evidence of byte integrity, selected source consistency and the recorded
emulation result. It does not prove ABI/runtime handoff compatibility between the
three components or any native driver operation. Archive digests are pinned from
GitHub metadata; the component receipts alone are not independent attestations.

## Reproduce after merging

No action is required to redo the successful check. To reproduce it in a checkout
containing this change, using the saved Downloads paths:

```sh
python3 scripts/check_artifact_set.py \
  --aura "$HOME/Downloads/UNQUALIFIED-candidate-aura.zip" \
  --kernel "$HOME/Downloads/UNQUALIFIED-candidate-kernel-3.zip" \
  --uboot "$HOME/Downloads/UNQUALIFIED-candidate-uboot.zip"
```

If Aura was not previously downloaded, save
[the original Aura artifact](https://github.com/frozen-infinity/pre-asahi/actions/runs/40401747548/artifacts/12689582635)
under that name. Select the original artifact, not a fresh rebuild. Filenames may
be changed in the command; the byte counts/digests must match. A mismatch stops
the check. Do not automatically replace the pins or use an incomplete download.

Only `reports/artifact-set.json` is written; input ZIPs are read-only. The report
contains hashes and source/run identifiers, not user paths or device identifiers.
A failed invocation prints STOP and does not produce a new success report; a
report from an earlier successful invocation may still be present. Reports and
the downloaded artifacts are ignored by Git and must not be committed.

ZIP members with unsafe paths, duplicates, encryption or special file types are
rejected, with count and uncompressed-byte limits. Nested xz package payloads are
read through Python's tar reader with size limits; no extraction API is used and
package symlinks are never followed. These limits supplement the exact ZIP pins.

## Development bundle contract

Keep each original archive and its sources/provenance. The eventual review bundle
must identify these inputs separately:

| Component | Role |
| --- | --- |
| Aura Stage 1 Mach-O/raw | Initial loader; enrollment/entry is unresolved |
| Aura Stage 2 raw | Runtime platform setup and subsequent handoff |
| U-Boot nodtb | Runtime DT import and EFI/OS loading; default J274 DT excluded |
| J713 kernel DTB + Image | Matching OS inputs, requiring runtime fixups |
| Diagnostic RAM initramfs | PID 1/logging proof; current QEMU probe is virt-only |
| Firmware/runtime state | Target-specific admission and reservations, not supplied by ZIPs |

This checker deliberately produces a report instead of concatenating a boot
image. Missing runtime state cannot be invented from a successful build. The
[pinned J713 importer has since passed its synthetic host suite](j713-handoff-fixtures.md).
The next gate is checking the saved OS tree's static contract and defining an
explicit bundle format that preserves its runtime handoff requirements. Only
after those are understood can bundle assembly be reviewed. Native entry,
logging and recovery for the actual Mac/firmware remain separate gates. No T7
layout, EFI boot file installation, startup-security change or hardware boot is
part of this check.
