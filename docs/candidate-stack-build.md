# Build the paired downstream candidate

This is the next build milestone toward a working system. It produces an Aura
bootloader package and prepares the matching downstream kernel configuration.
It does not install either component or establish a usable native desktop.

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
2. Choose **Run workflow**, branch **main**, component **both**, then start it.
3. Share the run link here. If it fails, keep the logs; do not change pins to make
   a failing source or signature check pass.

The manual workflow becomes available after it reaches the default branch. It
uses disposable GitHub ARM Linux runners. No commands are needed on your Mac,
Intel laptops or T7. Artifacts expire after seven days. Runner availability and
account usage limits can prevent a job starting.

## What the jobs actually do

Both jobs verify the pinned packaging/source agreement, the ALARM rootfs byte
count and SHA-256, and its detached GPG signature against the pinned signing key
before importing it into Docker. A changed `latest` archive fails closed: this
URL is not an immutable archive service. Reviewing a new pin is a separate change.

Container dependency updates run inside the disposable container. Upstream
recipes run as an unprivileged builder, without privileged Docker mode, host
devices, credentials, Docker socket or package installation on the runner host.
Only a fresh result directory is writable through a bind mount. The helper
refuses macOS and Intel Linux hosts. Do not adapt it to run directly on the Mac.

* **aura:** runs the pinned package build and makes a source archive alongside it.
  `AURA_PACKAGE_BUILT` means compilation and packaging completed, not enrollment
  or hardware execution.
* **kernel-config:** runs makepkg's prepare phase, including private bindgen,
  Rust setup, resolved configuration validation and generated headers. It saves
  the configuration and kernel release. `KERNEL_CONFIG_PREPARED` does not mean a
  full kernel, modules or DTBs were built.

Each attempt retains its log, recipe hashes, source pins, dependency versions,
output hashes and explicit unqualified status. Dependencies come from live ALARM
repositories and Rust downloads: this is not a hermetic or fully reproducible
toolchain snapshot. A build failure may expose packaging or dependency issues.
The CI grants read-only repository access and publishes no release or package
channel. Build outputs are development artifacts, not installation media.

Jobs allow two hours, four CPUs and 12 GiB container memory, with a 10 GiB free
space preflight. Resource exhaustion is a build failure, not a hardware finding.
The temporary image is removed by its unique tag; no global Docker cleanup runs.

## Validation and next gate

Local validation covers unit tests for input pins, signature-status parsing,
archive integrity and host refusal, plus shell syntax. The actual ARM package
and configuration jobs have not yet run. Their first result must be reviewed
before claiming either component builds through this pipeline.

Once both jobs pass, the next change can build the full paired kernel and run
emulator regressions. U-Boot, firmware admission, userspace, graphics and desktop
integration remain separate work. Native boot still requires a verified J713
entry, logging and recovery path for this Mac's firmware. No disk preparation,
boot policy changes, experimental boot or T7 erasure belongs to this milestone.
