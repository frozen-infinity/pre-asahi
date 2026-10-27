# Saved J713 OS tree: preparation and actual importer result

The workspace runner now uses the saved, exact-hash-verified kernel artifact
and the pinned production importer to prepare and probe the actual OS DTB on
the Mac. It does not alter the ZIP, install boot files or execute on bare metal.

## Observed result

| Input/output | Result |
| --- | --- |
| Original DTB SHA-256 | `95e6f0334a39f19af240c95a1678b43c34d5800bbd42263311f6ba540dd29dca` |
| Prepared static DTB SHA-256 | `ad139c2167a39792a61e9e38ef8b4196ed9b8ce6dd00d69e4be787ba1c3226e7` |
| Opt-in source identity | Kernel commit `311471f73e9919764bfb24acfe7eeb7c5230795a` |
| Prepared buffer capacity | 319488 bytes, including 256 KiB extra space and page alignment |
| Raw tree, no opt-in | Importer returns 0 (legacy), destination unchanged |
| Prepared tree, absent runtime source | Returns `-EINVAL`, destination unchanged |
| Prepared tree, wrong-model synthetic source | Returns `-EINVAL`, destination unchanged |
| Prepared tree, generic upstream synthetic runtime | Returns `-EINVAL`; diagnostic first failure `j713_cpus`; destination unchanged |

The generic fixture contains only its small test CPU topology. It is not a
capture of this M4 and does not satisfy the real OS tree's CPU import contract.
This is a diagnosed fixture mismatch, not a successful full handoff or proof of
a CPU driver bug. No copied firmware addresses or synthetic runtime imports are
saved as candidate boot inputs.

The prepared file is named **j713-STATIC-REVIEW-ONLY.dtb**. It is saved *before*
the synthetic import is attempted and has no imported/completion marker. Adding
an opt-in property establishes intent, not authentic runtime state or trust.
Its source identity is provenance metadata; the importer's syntax check is not
a cryptographic verification of that identity.

## Reproduction

The completed run used the saved `UNQUALIFIED-candidate-kernel-3.zip` in Downloads.
It compiled the host probe with the production importer and pinned libfdt on
macOS. To repeat after merging, with the locked fixture cache already populated:

```sh
python3 scripts/prepare_os_dtb.py \
  --kernel "$HOME/Downloads/UNQUALIFIED-candidate-kernel-3.zip"
```

If the cache is missing, first run `python3 scripts/j713_fixtures.py --fetch`
to fetch and validate the locked subset. Tools required: Python 3.9+, `cc` and
`dtc`, already installed on the user's development Mac. No dependencies are
installed automatically. The runner re-verifies the original archive, all
recorded kernel outputs, prior QEMU evidence and importer source hashes.

A new ignored `work/os-dtb-review-*` directory contains the preserved original,
prepared static tree, host probe, synthetic runtime fixture and explicit report.
The status is **STATIC_OS_DTB_PREPARED_RUNTIME_UNVERIFIED**. A zero command exit
means preparation/control checks completed; it does not mean synthetic import
or native boot succeeded. Read `synthetic_import_success` and the recorded return.
Neither the binaries nor generated trees/reports belong in the repository.

The C probe includes the unmodified production importer. Its stage diagnostics
run on disposable copies after the complete importer call and currently cover
reservations, CPUs, devices and Bluetooth only. `none` would not certify later
stages. Do not mistake this limited diagnostic for a second implementation of
the full importer. No hardware helper or private runtime capture is used.

## First entry: current evidence and the remaining work

Checked 2026-10-27: the official
[M4 support page](https://asahilinux.org/docs/platform/feature-support/m4/)
still lists no installer for M4 MacBook Air. The official
[tethered-boot guide](https://asahilinux.org/docs/sw/tethered-boot/)
starts from installing m1n1 and configuring its separate boot environment; it
does not document a macOS-only, external-SSD-only shortcut for this model. The
[m1n1 guide](https://asahilinux.org/docs/sw/m1n1-user-guide/) describes Stage 1
enrollment from the relevant recovery environment and Stage 2 payload loading.
Those generic instructions are not validation for this Mac/firmware or a reason
to replace the existing macOS boot object.

Mac-side testing remains authorized. Next, the generic fixture needs CPU
topology matching the actual saved OS tree (still explicitly synthetic), followed
by any other graph-contract failures exposed by that test. In parallel, first
entry needs an audited J713/current-firmware provisioning procedure that retains
macOS and establishes observable logs and recovery. A real runtime DT can only
come from a verified loader run; it cannot be manufactured from fixture success.
No installer model bypass, startup-policy command or target reboot is proposed
by this PR, and the T7 remains unchanged.
