# Emulated PID 1 milestone — 2026-10-26

Status: **EMULATED_PID1_PASS reported on the user's Intel Arch build host. Native M4 boot remains unproven.**

## Evidence reviewed

The user supplied the runner result and the nine passing unit-test results. The runner used QEMU 11.1.2, virt/gic-version=3, TCG, one CPU and 1 GiB RAM, with no disks/network and with QEMU's own generated DT. It accepted its Linux/virt/PID1 checks and completed in 3.51 seconds. Cleanup returned exit code 0. The raw console transcript was retained on the user's host but has not been independently read in this chat.

The reported input hashes match those supplied before this run:

| Artifact | SHA-256 |
| --- | --- |
| Kernel Image | 6144d97c7fb57561f64b8e61cd2dd38780d8b2069728ee2b0872a42b2a4663bc |
| Initramfs | 9c2ebaf763214f35c4d856c798b3847423852888d5f340fcff2e798d0523ed2f |
| Kernel .config | a47255608e14d4628660abefb6d6817e01272d4a4f0440f725700cebf8b55081 |
| Source lock | 09ab631cb99f1a5dea6ed4143584926bc83c521543786dc290042b825570cc25 |

The kernel header declares 16 KiB pages. Together with the accepted /init marker, this exercises the actual kernel loading the static diagnostic userspace, beyond the earlier QEMU user-mode binary check. It is a short emulated boot check, not independent reproduction, extended stability testing, native boot or an Arch desktop. No raw reports, host paths or device identifiers are committed with this summary.

## Completed development checks

- Cross-compiler AArch64 object check.
- Pinned Asahi kernel Image/j713 DTB build, with compatible identifiers checked.
- Pinned m1n1 build.
- Minimal static BusyBox build and QEMU user-mode checks.
- Deterministic initramfs structure and metadata inspection.
- Full-system emulated 16 KiB kernel-to-PID1 acceptance.

The build-and-emulation portion is complete. No more compiler installation, source refresh or repeated build is requested without a concrete reason. Keep the current artifacts, source lock, .config, compiler metadata and original logs intact.

## Native issues discovered during review

### M4 idle behavior differs from QEMU

Asahi's [Linux 7.2 progress report](https://asahilinux.org/2026/08/progress-report-7-2/) explains that M4 can lose core state on WFI and describes an idle-loop workaround. The pinned kernel's [arch/arm64/kernel/idle.c](https://github.com/AsahiLinux/linux/blob/94fb23346d522edf53722357c426a3e58030beea/arch/arm64/kernel/idle.c) implements early_param("idle") with wfi/yield/nop choices and defaults to WFI. Its parameter documentation also lists idle=nop.

Therefore the QEMU command line must not be copied verbatim to the Mac. A native test design must explicitly review the idle strategy, including the available idle=nop workaround. This is a planning requirement, not a ready-to-run boot command. Polling instead of sleeping changes CPU power behavior and requires a bounded hardware test plan. Do not rebuild or change the QEMU acceptance command merely to claim this hardware issue has been tested.

### Linux CPU limits do not constrain m1n1's own SMP setup

The pinned [proxyclient/tools/linux.py](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/proxyclient/tools/linux.py) invokes cpufreq_init and smp_start_secondaries before booting Linux. A kernel maxcpus argument would not prevent those loader-side actions. It imports m1n1.setup, which connects to the proxy and resets a panic counter. Do not treat this tool as a passive probe or launch it just to test a cable. The loader-side SMP/idle behavior must be understood separately from Linux's kernel arguments.

### Initial entry, firmware, transport and recovery remain unresolved

The Mac has only run macOS. There is no existing m1n1 environment to reuse. The installer model gate and firmware uncertainty remain as documented in [the boot-entry review](boot-gate-review.md). The [m1n1 hypervisor guide](https://asahilinux.org/docs/sw/m1n1-hypervisor/) does not pin an M4 macOS tracing target; its generic recovery instructions cannot establish compatibility with this machine. This is separate from native Linux boot. Lack of a firmware-table entry is uncertainty, not proof of an unavoidable failure.

## Next development work, before asking the user to execute anything

1. Establish a specific j713/firmware first-entry design based on upstream boot-object requirements. Identify the required per-OS internal boot components and preserve existing macOS/recovery. A T7 rootfs cannot supply these missing pieces. Do not implement support by merely adding j713 to an installer allowlist.
2. Audit m1n1's initialization path for the observed firmware, especially memory, reset vectors, idle and secondary-core handling. Separate native boot requirements from macOS-under-hypervisor requirements. Any code update should remain an isolated PR with source evidence and a concrete test boundary.
3. Establish an observable output/proxy transport for the actual port/cable and design failure recovery before selecting a native launch command. Do not assume a generic UART alias or successful emulation provides this transport.
4. Only once those are concrete, prepare a reviewable provisioning/hardware procedure identifying exact writes and rollback. The user's T7 erase permission does not authorize changing macOS boot policy or internal partitions implicitly.

No supported native provisioning procedure was established by this review. These are open development tasks, not a promise that a particular source patch or installer command will work. No hardware experiment is proposed by this PR.

## User steps now

No further commands, package changes or builds are needed for this result. Preserve the existing evidence. Leave the Mac and T7 unchanged while first-entry work is unresolved. The native acceptance criterion remains a real M4 kernel-to-PID1 transcript plus repeatable return to macOS; the emulated result must never be relabelled as that evidence.

## Follow-up: existing native mitigations located

The [deeper native-entry audit](native-provisioning-design.md) found that the pinned m1n1 already appends idle=nop/arm64.nowfxt, reserves the M4+ secondary-core CTRR region and switches to WFE at handoff. The earlier list above identified review requirements, not proven missing implementations. Reuse the existing code; no new mitigation patch is proposed. The user's preference is now to avoid risky target operations, so provisioning and disk changes remain deferred.
