# Upstream audit — 2026-10-25

Primary sources viewed via web; Git source downloads were unavailable in this execution environment (DNS restricted). Branch names and DTB targets were inspected online; no commit hash, full checkout, successful compilation, or hardware boot is claimed.

- [Asahi M4 support](https://asahilinux.org/docs/platform/feature-support/m4/): Air installer unavailable, device trees and early platform support present in linux-asahi. Boot framebuffer is listed; this alone does not demonstrate a boot on this machine. NVMe remains in development and key desktop peripherals remain unavailable. Recheck before every hardware campaign.
- [Device list](https://asahilinux.org/docs/hw/devices/device-list/): 13-inch Air = Mac16,12 / J713AP; 15-inch = Mac16,13 / J715AP; both T8132. T8142 is not the M4 Air SoC.
- [Linux](https://github.com/AsahiLinux/linux), branch `asahi`: [Apple DT build list](https://github.com/AsahiLinux/linux/blob/asahi/arch/arm64/boot/dts/apple/Makefile) contains `t8132-j713.dtb` and `t8132-j715.dtb`. Existing device trees should be extended rather than duplicated. The viewed J713 source has an inconsistent model-year string; use compatible/board IDs for matching, not its marketing-year text.
- [m1n1](https://github.com/AsahiLinux/m1n1), branch `main`: existing Apple boot initialization, proxy and experimentation framework. Its README documents builds and payload formats. M4-related changes do not establish end-to-end M4 Air support. Preserve the license at the exact revision: recent README describes a MIT-to-GPL transition.
- [U-Boot](https://github.com/AsahiLinux/u-boot): later UEFI/distro integration; unnecessary for the initial direct-kernel diagnostic target. No unverified branch is pinned here.
- [Installer](https://github.com/AsahiLinux/asahi-installer): inspect model/firmware gating in a later review; do not bypass it. Not downloaded or invoked by this scaffold.
- [Tethered boot](https://asahilinux.org/docs/sw/tethered-boot/): architectural reference for m1n1 and direct versus hypervisor testing. Its generic preparation steps change boot state and are not an M4 authorization or compatibility guarantee.

Arch Linux ARM userspace is downstream of a functioning platform kernel. Phase 1 deliberately uses a minimal independent diagnostic userspace; it is not an Arch root filesystem. After native boot, investigate 16 KiB page compatibility, package provenance/signatures, firmware distribution, boot integration, and update/recovery design before preparing Arch packages. Follow current [Asahi distribution guidelines](https://asahilinux.org/docs/alt/policy/), confirming the current canonical location first.

Before contributing, review the current [Asahi AI policy](https://asahilinux.org/slop/) and each repository's contribution rules. This scaffold was AI-assisted. Do not submit it as human-authored upstream driver work; maintainers' rules apply. No upstream submissions were made.
