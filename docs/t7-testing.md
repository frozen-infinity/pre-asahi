# Testing with a separate Samsung T7

## Intended storage layout

| Component | Phase 1 | Later, after support is proven |
| --- | --- | --- |
| Existing macOS and Apple recovery | Leave unchanged | Preserve recovery and normal macOS boot |
| Apple-authorized boot entry / initial Asahi components | No provisioning in this PR | A separately reviewed procedure may need internal storage |
| Linux kernel + diagnostic userspace | Build artifacts; eventual RAM payload | RAM payload or reviewed boot-chain storage |
| Experimental Arch root filesystem | Not created | Dedicated T7 partition, only after USB storage and recovery are validated |
| Logs and source/build trees | Ordinary project folder on development host or existing T7 filesystem | Continue retaining evidence separately from test rootfs |

The T7 is a USB device. A USB-C connector does not establish functioning Linux USB, IOMMU, controller, or storage support. Do not equate it with a Thunderbolt PCIe disk. The actual T7 model, bridge, cable, port, firmware and sustained power behavior must be recorded when USB testing becomes possible.

[Asahi's boot guide](https://asahilinux.org/docs/alt/boot-process-guide/) documents an internal ESP in the standard stage-1/stage-2 chain. Its [M4 status table](https://asahilinux.org/docs/platform/feature-support/m4/) currently does not list USB2/USB3 as supported. These are two independent gates. Neither an external rootfs nor a generic UEFI-on-USB guide removes them. An m1n1 proxy transport, if verified, is separate from native Linux USB mass-storage support.

## What to do now

1. Preserve the T7's current contents. No formatting or partitioning is needed. Keep important backups on separate media.
2. Run the README preparation commands on macOS. If storing the clone on the T7, first open the already mounted volume in Finder and open Terminal in an existing folder there. Confirm the destination yourself; do not create a guessed `/Volumes/...` path. Cloning writes project files only.
3. Record the exact Air model (13/15-inch), macOS version/build, T7 variant/capacity, whether it has data, and availability of a second development host. Disk Utility's Info panel can show the current format and connection without changing anything; review identifiers before sharing.
4. Wait for a PR with a validated boot/logging path for that exact model and firmware. The next hardware step requires an independently reviewed return-to-macOS procedure. No installer bypasses, recovery commands, or disk changes are included here.

An existing exFAT volume may be adequate to carry archives and logs, but it does not preserve Unix file semantics needed for a Linux rootfs, and case-insensitive filesystems can break kernel source checkouts/builds. Use a suitable case-sensitive development filesystem on the Linux build host for kernel compilation. Do not reformat the T7 just to run these Python checks. Later filesystem selection and partition sizing will be a separate concrete proposal based on its actual contents and capacity.

## Gates before an external rootfs test

- Phase 1 native RAM-only proof with exact model, locked sources, full logs and verified macOS recovery.
- Native Linux USB host/controller and storage support validated for the actual port, cable and T7, without depending on the prospective rootfs.
- Read-only T7 recognition and repeated reads succeed before any write experiment. A later kernel configuration must explicitly enable the required block/USB/storage/filesystem drivers, built in or included in initramfs. The Phase 1 config disables the block layer and cannot boot a T7 rootfs.
- A reviewed disk plan identifies the external physical device by more than an unstable disk number, preserves unrelated data, and records any required internal boot changes. Formatting needs explicit authorization for the identified device; owning a spare T7 does not authorize erasing it.
- Only then stage a verified Arch Linux ARM userspace, first mount read-only, collect evidence, and expand testing deliberately. Avoid broad installer auto-discovery that could select the internal drive.

No external boot, T7 compatibility, USB functionality or full desktop support has been demonstrated by this repository.
