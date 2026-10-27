# Transition from component tests to Mac bring-up

The final goal is native Linux on the M4 MacBook Air. On 2026-10-27 the user
clarified that necessary testing and running code on the Mac are within scope.
The earlier build-only preference is no longer a blanket restriction. Work should
advance toward Mac execution as the actual entry/logging/recovery requirements
are established. No new disk or startup-security action is performed by this
documentation update.

## Linux importer result confirmed

[Run 40500142540](https://github.com/frozen-infinity/pre-asahi/actions/runs/40500142540)
passed the project tests and the pinned upstream importer suite on Ubuntu GCC
13.3.0 with DTC 1.7.0: 56 synthetic imports and five padding compile checks.
This independently reproduces the earlier successful Apple clang/DTC host run.
No private runtime capture or hardware helper was used in either run.

## Saved OS DTB inspected on the Mac

The J713 DTB was read from the saved, previously hash-verified full kernel archive
and copied only into ignored workspace scratch storage for `fdtget` inspection.
Its root compatible is `apple,j713 apple,t8132 apple,arm-platform`. Its `/chosen`
contains the framebuffer placeholder, stdout path and downstream disk/DAPF
handoff policy properties. It does **not** contain `u-boot,j713-dtb-source`.

This matters because the
[pinned production importer](https://github.com/aurora-silicon/u-boot/blob/7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c/arch/arm/mach-apple/j713_fdt.c)
returns the legacy result (0) when that property is absent. An opted-in OS DT
requires a NUL-terminated 40-character lowercase hexadecimal source identity,
matching J713/T8132 identities, bounded valid runtime/OS trees and sufficient
buffer capacity. Completion of its DT import still does not prove live firmware,
input-device or driver readiness.

The raw build DTB is therefore an input to a bundle-preparation step, not a
finished runtime handoff tree. Adding its marker blindly would also be
insufficient: the live runtime source, required topology, reserved memory and
buffer allocation must satisfy the importer. Its final buffer capacity must
include the required room; padding the raw DTB is not itself a hardware test.
The full boot flow, including EFI/OS-DT selection, must be verified rather than
assuming an enabled U-Boot configuration completes it automatically.

## Concrete next work

Prepare a workspace-only OS-DT handoff candidate that records its kernel source
identity and explicit buffer contract, preserves the original DTB and validates
it with the actual production importer. Extend the harness to use the saved OS
DTB with synthetic runtime inputs and expose topology failures directly. These
tests must remain distinguishable from genuine runtime data. No firmware
addresses, calibration data, device serials or entropy may be invented for a
native run from a successful synthetic test.

In parallel, establish a model/firmware-specific entry and observation procedure
for the Mac that has only run macOS. The user has authorized necessary Mac-side
testing; an earlier software-only restriction should not block useful target
work. The unresolved first-entry/recovery mechanism still must be made concrete
before presenting a native boot command. T7 rootfs storage alone does not supply
that mechanism. Internal erasure, startup-policy changes and installer bypasses
are not implied by the testing clarification.
