# Phase 1: prepare, then prove a minimal native boot

## Work packages and gates

1. **Identify**: collect `reports/hardware.json` on the actual target. Match Mac16,12 → j713 or Mac16,13 → j715, Apple M4, T8132 board mapping; record OS version/build. Unknown/mismatched values stop hardware testing. Record firmware version separately with privacy review if the allowlisted report lacks it.
2. **Pin and build**: fetch writes exact upstream commits. Review source changes, m1n1 firmware/SPTM handling, board DT and kernel config. Build on appropriate hosts. Preserve source lock, .config, compiler versions, DTB, Image and checksums. A clean build is preparation evidence only.
3. **Establish lab path**: confirm upstream M4 Air guidance for the exact firmware, a second host, verified cable/port and actual m1n1 proxy or hardware UART observability. Confirm power and a documented return-to-macOS path. RAM payloads still require a boot entry; there is no promise of disk-free first-time m1n1 provisioning. If provisioning needs storage/security changes, prepare a separate reviewed procedure and obtain authorization outside this milestone. Stop here if no supported route exists.
4. **Attempt minimal payload** only after gate 3. Use upstream direct-kernel tooling for the locked revision and exact DTB, with compressed Image and initramfs. Capture the complete host transcript from m1n1 entry onward. Do not guess console parameters: verify DT aliases, chosen stdout path and current m1n1 forwarding. Do not substitute the hypervisor to claim native success. This scaffold intentionally omits a hardware launch command.
5. **Accept** only when native m1n1 → Linux kernel banner → matching board → PID 1 marker is captured, the source lock/config/artifact hashes are attached, and two cold-start runs return to macOS using the reviewed procedure. A framebuffer photo alone cannot establish all criteria. Otherwise classify the last observed boundary and retain failure logs.

## Diagnostic payload

`initramfs` packs a user-supplied static AArch64 BusyBox and `/init` into deterministic newc+gzip. `/init` mounts only proc/sysfs/devtmpfs, prints the marker and kernel/compatible information, then sleeps. No interactive keyboard, NVMe, network, graphics acceleration, or Arch userspace is required. It does not mount any persistent filesystem. No reboot is automated. Inspect the binary's provenance and test the archive in an ARM64 emulator if available before hardware use; emulator success is not M4 proof.

Suggested candidate kernel command line, to be reviewed against locked source: `rdinit=/init loglevel=8 ignore_loglevel`. Add a console/earlycon only after its transport is verified. Initial config disables PCIe and the block layer to reduce accidental persistent storage access. Do not enable unverified peripherals just to reach userspace.

## Failure triage and evidence

Record date, model, OS/firmware, host/cable/port, boot mode (native/hypervisor), source lock, compiler versions, final config hash, payload hashes, exact reviewed launch arguments, full log, last successful boundary, and recovery result. Keep raw logs private until reviewed for identifiers. Distinguish no output from no execution. Never repair a failed boot by copying an unrelated board DT or disabling installer checks.

## Eventual desktop roadmap

After Phase 1: interrupts/timers/SMP and memory stability → validated storage/IOMMU and recovery-safe Arch rootfs → USB and internal input/network → display/GPU → power, suspend and battery → audio/camera and distribution updates. Reorder using upstream dependencies and actual evidence; do not promise dates. Speaker work requires upstream protection/calibration infrastructure. Prefer small independently validated upstream fixes over a parallel driver stack.
