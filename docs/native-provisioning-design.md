# Native provisioning design: source findings and current limits

Review date: 2026-10-26. Target: j713/T8132. Source pins remain m1n1 `51b747dced07a58eacf5dabc31ed6f00bcfa20fd` and Linux `94fb23346d522edf53722357c426a3e58030beea`.

The user can potentially borrow a modern Mac for recovery but strongly prefers to avoid risky operations. Current work therefore remains source analysis, read-only identification and build-host/emulator tooling. No T7 erase, external macOS installation, security-policy change, custom boot-object installation or native experiment is requested. Earlier permission to wipe the T7 is not an instruction to do so now.

## A deeper source review corrects the earlier gap list

The previous milestone note correctly identified idle/SMP as M4-specific concerns, but it did not yet inspect the native handoff implementation. The pinned source already contains important handling:

| Area | Evidence at the pinned revision | Meaning and limit |
| --- | --- | --- |
| M4 CPU detection | [src/chickens.c](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/src/chickens.c): T8132 Donan cores use features_m4; unlisted boolean fields are zero | Native M4 feature selection exists; no new CPU table entry is needed for this work |
| Idle and timed-wait arguments | [src/kboot.c](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/src/kboot.c): dt_set_chosen appends `idle=nop arm64.nowfxt` when Apple sysregs are locked | The idle workaround is already supplied by native DT preparation; avoid duplicating or removing it |
| Locked reset vectors | [src/smp.c](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/src/smp.c): conditional RVBAR write and mismatch diagnostic | Do not write locked reset registers as a supposed new fix; behavior still needs hardware validation |
| Secondary-core protected memory | src/kboot.c adds an M4+ CTRR region to FDT reservations | The kernel's memory layout depends on loader DT fixups; a plain compiled DTB is not a ready handoff |
| Parked secondary cores | src/kboot.c calls smp_set_wfe_mode(true) before the next stage | Linux CPU limits are still separate from loader SMP initialization, but WFE handoff handling already exists |
| Guarded execution | [src/main.c](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/src/main.c) guards gxf_init with supports_gxf; [src/utils.c](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/src/utils.c) also checks the mmu_sprr feature | Raw/native entry and running Apple's XNU under a hypervisor are different cases; lack of an M4 macOS tracing target does not prove native Linux cannot boot |
| Kernel idle option | [arch/arm64/kernel/idle.c](https://github.com/AsahiLinux/linux/blob/94fb23346d522edf53722357c426a3e58030beea/arch/arm64/kernel/idle.c) parses idle=nop | The pinned Linux side has the option consumed by m1n1's existing handoff |

These are code facts, not a claim that every path works with the target firmware. We should reuse this infrastructure rather than introduce speculative replacement drivers or firmware table entries. No upstream patch is justified merely by the earlier unverified gap list.

## The boot-object boundary

[Apple Platform Security](https://support.apple.com/en-euro/guide/security/sec7d92dc49f/web) describes owner-authorized custom boot objects under Permissive Security. This is not achieved by putting an ARM64 kernel on a USB drive. LocalPolicy, the selected OS identity and its paired recovery environment matter.

The local `kmutil` help was inspected without configuring anything. It describes custom raw boot objects as a recovery-only operation. [Asahi's user guide](https://asahilinux.org/docs/sw/m1n1-user-guide/) likewise describes raw stage-1 installation into a specific OS/stub and paired recovery. Neither source establishes a successful procedure for this j713/current firmware. No recovery command is supplied here as an instruction.

Two candidate environments were evaluated conceptually:

| Candidate | What is established | Why it is deferred |
| --- | --- | --- |
| Normal Apple macOS installation on the T7, later considered as an expendable boot identity | [Apple supports external macOS startup](https://support.apple.com/en-ie/111336), with an operational internal startup disk | Installing macOS and later replacing its boot object are distinct steps. External startup still depends on the Mac; installer/security updates may affect firmware. No custom-object compatibility was established, and the user does not want risky changes |
| Dedicated internal test OS/stub | The generic Asahi boot design uses a separate per-OS identity | It changes internal storage/boot state and the standard installer does not support j713. No installer bypass or repartitioning is proposed |

The T7 remains useful test storage for a later rootfs; it is not a whole-machine isolation boundary. The evaluated candidates are not executable plans or recommendations to prepare those disks now.

## Native observability is distinct from the m1n1 proxy

The pinned main.c initializes USB console/proxy in normal developer builds when no valid payload is run. It also shuts down its USB I/O devices before next-stage entry. Successful USB proxy enumeration, if later tested, would therefore not prove a native Linux USB console exists after handoff.

The j713 common [device tree](https://github.com/AsahiLinux/linux/blob/94fb23346d522edf53722357c426a3e58030beea/arch/arm64/boot/dts/apple/t8132-jxxx.dtsi) enables serial0 and names it as stdout. That does not establish a cable path to the Arch laptop. Asahi's [serial-debug document](https://asahilinux.org/docs/hw/soc/serial-debug/) describes special USB-PD debug arrangements, largely in M1 terms; it is not proof that the user's standard T7 cable exposes the j713 debug UART. No adapter purchase or debug-mode command is requested without confirming M4 applicability. A hypervisor virtual UART would test a different boot mode.

Before proposing a native kernel attempt, specify which exact output path survives handoff and what observation ends the attempt. A framebuffer may assist early diagnosis, but its behavior on this firmware is also untested. Preserve the native transcript requirement; do not relabel the QEMU log.

## Recovery assumptions and write inventory

[Apple's revive/restore procedure](https://support.apple.com/en-us/108900) uses another Mac with macOS 14 or later. The user's Arch laptops are build/debug hosts, not substitutes for that documented Finder workflow. Borrowing a Mac may be possible, but this does not make an experiment risk-free or establish recovery as tested.

| Stage | Potential changes | Current action |
| --- | --- | --- |
| Source audit | Local report on the development host | Allowed; optional helper below |
| External macOS preparation | T7 contents plus Apple-managed boot/installation state; possible firmware effects | Deferred |
| Custom boot-object authorization | Selected OS boot object and per-OS security policy; target identity must be known | Deferred; no commands provided |
| First m1n1-only boot | Executes experimental initialization on the Mac | Deferred; no Linux payload should be the first observation boundary |
| Return through startup options / paired recovery | Depends on the exact OS identity and machine state | Must be designed and verified before hardware experimentation |
| DFU revive | Firmware/recovery updates; Apple describes it as non-erasing | Fallback reference only, not a guaranteed rollback |
| DFU restore | Erases the Mac | Not an acceptable assumed rollback under the user's current preference; no action proposed |

No storage device was modified. Read-only disk/IODeviceTree queries were unavailable in this restricted session; no privileged retry or security change was attempted. Filtered firmware information from the earlier successful helper remains identification evidence, not a supported-firmware determination.

## Optional host-side audit

The new helper reads only the existing pinned source trees after checking their Git revisions, origin URLs and tracked cleanliness. It locates reviewed text anchors, records source hashes/line numbers, and writes reports/native-source-audit.json. It does not import proxy clients, contact the Mac, download code, build artifacts or run boot/recovery tools. Text anchors are navigation aids, not semantic/runtime proofs. Changed pins require a fresh source review.

On the Arch laptop, in a clean existing clone (retain local changes first):

```sh
git fetch origin
git switch --track origin/native-entry-audit
python3 -m unittest discover -s tests -v
python3 scripts/native_source_audit.py
```

If the branch already exists, use `git switch native-entry-audit`. Do not rebuild or re-fetch upstream sources. Exit 0 means the static audit completed with the expected anchors; status stays STATIC_SOURCE_AUDIT_ONLY and native_boot_proven stays false. Sharing the report is optional; there is no target-side action needed from the user now.

## Validation and practical outcome

All twelve local Python tests passed, including revision-change refusal and the invariant that matching source text cannot become hardware approval. The eight audit groups were located in source contents retrieved at the exact pins. The Git checkout checks remain to be exercised on the user's actual source trees; no full source clones or Mac boot were required for this review. CLI help and documented shell syntax passed.

The practical outcome is a narrower native task: establish owner-authorized first entry on a recoverable expendable OS identity and native logging for this firmware. Existing idle/reset/CTRR/WFE code should not be rewritten without a demonstrated defect. There is no suitably validated low-risk native procedure to offer for the daily-use Mac yet. Continue source/emulation work and external upstream review; keep all target changes deferred unless the user later chooses a concrete experimental procedure with its actual write/recovery consequences understood.
