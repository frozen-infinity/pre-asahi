# Path to a working native system: maintained-source candidate evaluation

Reviewed 2026-10-26. The final target remains native Linux on the user's M4 Air, with Arch Linux ARM userspace and eventual desktop support. QEMU is a regression tool, not a substitute for the final platform. The user's preference to avoid risky target changes remains in force.

## Decision

Preserve the proven Asahi kernel/m1n1/initramfs bundle. Evaluate a separately pinned downstream stack that already carries j713 platform work before attempting to write replacement drivers. This PR adds an isolated device-tree compilation tool and records actual offline compilation results. It does not select an installer or authorize a native boot.

The earlier source-anchor checks established what exists in our baseline; repeating them cannot fill the remaining platform gaps. The next useful implementation lane is reproducing and understanding a coherent maintained driver/loader/userspace stack on the build host. Hardware qualification will still be necessary eventually; we cannot promise a usable native desktop from code inspection or without some hardware experimentation.

## Current candidates and evidence boundaries

- **Asahi** remains the baseline and preferred infrastructure. Its [M4 support table](https://asahilinux.org/docs/platform/feature-support/m4/) does not list an M4 Air installer. Keep the tested pins and artifacts; do not refresh them silently.
- **Aurora Silicon** publishes a [j713 hardware report](https://aurorasilicon.org/devices/) claiming broad support, and has public kernel, loader, Mesa and Arch Linux ARM integration sources. Its [ALARM README](https://github.com/aurora-silicon/alarm-aurora/blob/ac3b14d017cb5c316d21a8af3b3e38e40390b388/README.md) explicitly separates development artifacts from physical installation/update/reboot qualification. Its [download page](https://aurorasilicon.org/docs/download/) still says coming soon, while its repositories describe developer artifacts. Treat those as different maturity signals. A feature-page claim does not qualify installation on this Mac or firmware.
- **Gravity Linux** has an [M4 Mac mini developer alpha](https://gravitylinux.org/blog/early-alpha-m4-mac-mini/), while its [device table](https://gravitylinux.org/) still lists M4 Air as WIP. The mini release cannot be applied to j713 by chip-family analogy. No installer was run.
- **Omarchy-M4-Native:** the historical-only description in this review was stale. The [2026-10-28 recheck](native-entry-recheck.md) records exact-model native desktop reports and an experimental internal-SSD installer at an immutable source revision. Its stack, host-firmware qualification and write/recovery consequences differ from ours; no installer was executed or adopted.

Aurora is therefore a candidate for source/build evaluation, not a recommendation to install. No party was contacted and no downstream code was executed on the Mac. No broad downstream claims have been independently verified here.

## Reproducible source selection

For the candidate DT, use Aurora's ALARM packaging pin rather than its moving integration branch:

- Packaging snapshot: `aurora-silicon/alarm-aurora` at `ac3b14d017cb5c316d21a8af3b3e38e40390b388`.
- Its [sources.json](https://github.com/aurora-silicon/alarm-aurora/blob/ac3b14d017cb5c316d21a8af3b3e38e40390b388/sources.json) selects kernel `311471f73e9919764bfb24acfe7eeb7c5230795a`, version 7.3.0. It also pins Aura, U-Boot and Mesa separately. This record is an input to review, not qualification of their composition.
- The kernel [PKGBUILD](https://github.com/aurora-silicon/alarm-aurora/blob/ac3b14d017cb5c316d21a8af3b3e38e40390b388/packages/linux-aurora/PKGBUILD) has its own config/toolchain/bindgen requirements. Do not transplant our distro-managed Rust setup or run its native AArch64 package recipe directly on the Intel host without an isolated build design.
- The README still mentions an older shared kernel version in one passage. For this compilation, the exact sources.json pin above was used, not inferred README prose.

Only DTS/DTSI and required dt-binding headers were fetched, through read-only source APIs at the exact commits. Nothing from the source tree was executed. The compiler runs our own fixed Clang/dtc command, not an upstream Makefile. No Apple firmware or raw machine captures are needed for this step.

## Actual offline compilation results

Both source graphs were preprocessed and compiled locally using Apple Clang 21.0.0 and dtc 1.8.1:

| Profile | Included source files | DTB size | Aliases | dtc warning lines | SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| Tested Asahi baseline | 8 | 32,179 bytes | 1 | 1 | 9f6ab3cfa738216e25f81eb258750cddd354e0f6a315c3419df8f1f3792722b5 |
| Aurora ALARM candidate | 15 | 54,528 bytes | 17 | 10 | 95e6f0334a39f19af240c95a1678b43c34d5800bbd42263311f6ba540dd29dca |

Both identify `apple,j713 apple,t8132 apple,arm-platform`. The baseline DTB is byte-identical to the user's earlier kernel-build artifact. The candidate compilation succeeds but emits warnings involving reserved-memory names, display bus/address cells, duplicate placeholder unit addresses and an alias name. Warnings were retained, not suppressed or treated as driver validation. No dt-schema validation or full candidate kernel build was performed.

The candidate describes additional USB, PCIe/radio, MTP input, SMC/PMIC, GPU and display topology. **An alias is not a working device.** In the compiled candidate, ANS/storage, its mailbox/SART, PMP and parts of the display path still have disabled status properties. Other alias targets omit status, and ancestor status was not evaluated. Some nodes have placeholder addresses and board/firmware data expected from the downstream handoff. This is why the candidate DTB must not be paired blindly with our older kernel or m1n1.

## Host-side implementation

`configs/dtb-candidates.json` holds the independent exact source pins. `scripts/dtb_candidate.py` fetches only the literal include graph over HTTPS or verifies a supplied offline cache receipt, preprocesses/compiles it, checks the root compatible list, and records source hashes, DTB hash, tool versions and aliases in a fresh work directory. It confines include paths to the reviewed source areas and rejects macro includes requiring additional review. Cache receipts detect changed cached bytes; they are provenance records, not signed authenticity proofs.

This tool never runs an installer, mounts an image, accesses a physical device, builds a kernel, installs packages or modifies sources.lock.json, the existing source checkouts, or the successful artifacts. Downloaded source and generated DTBs stay under ignored work/ directories and are not committed. Build logs remain available if Clang/dtc fail.

Optional reproduction on the existing Arch host, from a clean checkout after preserving local changes:

```sh
git fetch origin
git switch --track origin/working-system-candidate
python3 -m unittest discover -s tests -v
python3 scripts/dtb_candidate.py --profile asahi-baseline
python3 scripts/dtb_candidate.py --profile aurora-alarm-candidate
```

If the branch exists locally, use `git switch working-system-candidate`. The existing clang/dtc/fdtget tools are used. Fetching these small source graphs needs network; the local compiler validation here used API-fetched offline caches. The helper's direct raw-HTTPS fetch path has not yet been exercised end-to-end in this session. No sudo or new package transaction is needed for this step.

## Next implementation milestone

1. Review the selected downstream kernel configuration and required loader/Aura ABI together. Identify which fixups/firmware inputs populate the disabled or placeholder nodes and which are actually required for a minimal j713 boot. Do not mix independently selected moving branches.
2. Prepare an isolated, pinned build recipe for that coherent candidate on the Arch development machine, without replacing our baseline or host toolchain. Reproduce a kernel/DTB build and regress the RAM-only userspace on QEMU where applicable. Compile success will still not prove driver function.
3. Only then consider a reviewable native test environment and observability design consistent with the user's risk preference. A spare SSD does not isolate firmware/boot policy, and borrowing a recovery Mac does not make an experiment risk-free.
4. Once native platform boot, input/output, thermal/power handling and USB storage are qualified, stage the real Arch userspace and validate updates/recovery. A usable desktop additionally needs a compatible graphics/firmware/userspace stack, not just a kernel that reaches PID 1.

These are ordered engineering milestones, not a schedule or an assurance that hardware experimentation can be eliminated. Current native installation and T7 erasure remain deferred. No additional user action is necessary now: the offline DT compilation above has already run.

## Validation

Seventeen local Python tests passed, including source-include confinement, comment/macro handling, changed-cache/revision rejection, and a complete mocked HTTPS include-graph fetch/receipt round-trip. CLI help and documented Bash syntax passed. Both pinned DT source graphs actually compiled and their root compatibility/aliases were inspected. The source receipt verifier ran against those complete cached graphs. No candidate kernel, desktop, firmware handoff, installation or hardware boot was tested; no external driver code or binaries were vendored into this repository.
