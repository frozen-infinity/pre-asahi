# Build the paired downstream candidate

Aura packaging and matching kernel preparation passed in
[run 40401747548](https://github.com/frozen-infinity/pre-asahi/actions/runs/40401747548).
The next milestone builds the complete kernel Image, modules and device trees,
then attempts a RAM-only PID 1 test on QEMU virt. It does not install components
or establish a usable native desktop.

## Why this pairing

The [pinned ALARM kernel recipe](https://github.com/aurora-silicon/alarm-aurora/blob/ac3b14d017cb5c316d21a8af3b3e38e40390b388/packages/linux-aurora/PKGBUILD)
requires Aura, Rust 1.99.0, a private bindgen 0.73.2 build and shared configuration
fragments. A compiled J713 device tree alone does not reproduce that stack.
The [Aura recipe](https://github.com/aurora-silicon/alarm-aurora/blob/ac3b14d017cb5c316d21a8af3b3e38e40390b388/packages/aura/PKGBUILD)
builds separate Stage 1 and ESP Stage 2 artifacts. We build those upstream recipes
at the packaging snapshot already selected in the candidate review:

| Input | Commit |
| --- | --- |
| alarm-aurora packaging | `ac3b14d017cb5c316d21a8af3b3e38e40390b388` |
| Linux | `311471f73e9919764bfb24acfe7eeb7c5230795a` |
| Aura | `553b566f69275ff4e46ee6542a7236fb80a333a2` |

The existing Asahi baseline builds and source lock remain separate. Never combine
this candidate DTB with the baseline kernel or m1n1 as an assumed working bundle.

## Your steps

After merging this PR:

1. Open the repository's **Actions** tab and select **Candidate stack build**.
2. Choose **Run workflow**, branch **main**, component **kernel**, then start it.
3. Share the run link here. If it fails, keep the logs; do not change pins to make
   a failing source or signature check pass.

The manual workflow becomes available after it reaches the default branch. It
uses disposable GitHub ARM Linux runners. No commands are needed on your Mac,
Intel laptops or T7. Artifacts expire after seven days. Runner availability and
account usage limits can prevent a job starting.

## What the jobs actually do

All build modes verify the pinned packaging/source agreement, the ALARM rootfs byte
count and SHA-256, and its detached GPG signature against the pinned signing key
before importing it into Docker. A changed `latest` archive fails closed: this
URL is not an immutable archive service. Reviewing a new pin is a separate change.

Container dependency updates run inside the disposable container. Upstream
recipes run as an unprivileged builder, without privileged Docker mode, host
devices, credentials or Docker socket. Candidate packages are never installed.
Only a fresh result directory is writable through a bind mount. The helper
refuses macOS and Intel Linux hosts. Do not adapt it to run directly on the Mac.

* **aura:** runs the pinned package build and makes a source archive alongside it.
  `AURA_PACKAGE_BUILT` means compilation and packaging completed, not enrollment
  or hardware execution.
* **kernel-config:** runs makepkg's prepare phase, including private bindgen,
  Rust setup, resolved configuration validation and generated headers. It saves
  the configuration and kernel release. `KERNEL_CONFIG_PREPARED` does not mean a
  full kernel, modules or DTBs were built.
* **kernel:** repeats preparation and calls the pinned recipe's actual `build()`
  function, with its `_make` wrapper, to build `Image modules dtbs`. It preserves
  the downstream configuration, including debug/BTF settings. It saves Image,
  Apple DTBs (requiring J713), module objects in `modules.tar.zst`, symbol/order
  metadata, exact tracked kernel sources and the recipe inputs. It never runs
  the kernel package/install functions. `FULL_KERNEL_BUILT_QEMU_PENDING` records
  compilation; the QEMU verdict is a separate result.

The **both** choice still selects Aura plus configuration preparation. Use
**kernel** for this new milestone; it does not rebuild Aura unnecessarily.

After a full build, CI installs Ubuntu's emulator and C build tools on the
disposable runner VM. It compiles a tiny static AArch64 diagnostic `/init` with
64 KiB ELF load alignment, validates its architecture/static linking, then
creates a gzip/newc RAM filesystem. This is a CI probe, separate from the earlier
BusyBox initramfs. The probe checks PID=1, mounts proc/sysfs, validates
`linux,dummy-virt`, and prints the existing acceptance marker. QEMU uses TCG,
one CPU, 1 GiB RAM, no disk or network, and its generated virt DT; Aura and the
Apple DTB are not executed. The helper binds Image/config/J713 DTB hashes to the
successful pinned build receipt before testing the Image. The existing baseline
QEMU command still works without candidate arguments.

`qemu/qemu-virt-*/result.json` must say `EMULATED_PID1_PASS`; a green compile step
alone is insufficient. Its console log and exact input hashes are retained.
This tests generic kernel-to-userspace loading, not J713 drivers, module loading,
Aura handoff, display, USB/T7 access or native boot.

Each attempt retains its log, recipe hashes, source pins, dependency versions,
output hashes and explicit unqualified status. Dependencies come from live ALARM
repositories and Rust downloads: this is not a hermetic or fully reproducible
toolchain snapshot. A build failure may expose packaging or dependency issues.
The CI grants read-only repository access and publishes no release or package
channel. Build outputs are development artifacts, not installation media.

Jobs allow four hours, four CPUs and 12 GiB container memory, with a 10 GiB free
space preflight. Resource exhaustion is a build failure, not a hardware finding.
The full debug kernel can need substantially more disk than the preflight
minimum; a hosted-runner disk failure requires a larger disposable builder or a
separately reviewed build-profile change. No automatic configuration reduction,
global cleanup or source pin refresh is performed to force a pass.
The temporary image is removed by its unique tag; no global Docker cleanup runs.

## Validation and next gate

Local validation covers unit tests for input pins, signature-status parsing,
archive integrity, host refusal and candidate artifact/receipt binding, plus
shell syntax. The first CI run's decoded logs confirmed Aura 0.1.0.r20261022-4
packaging and preparation of Linux 7.3.0-1-2-ARCH, including Rust/bindgen code
generation. The full kernel build and candidate emulator job have not yet run.
The Linux-only C probe is compiled/checked on CI; macOS headers cannot check its
Linux mount calls.

Once compilation and candidate emulation pass, review the archived evidence
before extending stack integration. U-Boot, firmware admission, userspace, graphics and desktop
integration remain separate work. Native boot still requires a verified J713
entry, logging and recovery path for this Mac's firmware. No disk preparation,
boot policy changes, experimental boot or T7 erasure belongs to this milestone.
