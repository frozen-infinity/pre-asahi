# First native stage: proxy-only candidate and storage boundary

This step prepares a separately identified first-entry candidate. It does not
enroll it, boot it, change firmware policy, resize storage or erase the T7.
The existing Aura, kernel, U-Boot and QEMU-tested artifacts remain unchanged.

## The first hardware observation

A future first attempt should establish only that a reviewed Stage 1 runs, shows
its exact build tag on the inherited framebuffer, reaches its proxy, and permits
a demonstrated return to macOS. No kernel, OS DTB, initramfs or ESP Stage 2 is
attached to this candidate. Linux PID 1 remains a later native milestone.

The candidate retains normal Aura platform initialization and a powerful proxy.
It is **not a read-only hardware monitor**. USB commands can write memory or run
code once it is booted. It is not executed in QEMU: a generic virt machine cannot
validate Apple Stage 1 hardware initialization. Firmware framebuffer output and
USB transport remain untested on our Mac with this build.

## Exact build profile

Use Aura `553b566f69275ff4e46ee6542a7236fb80a333a2`, unchanged from the selected
stack, in a new isolated work tree:

| Setting | Purpose |
| --- | --- |
| `RELEASE=0` | Keep the framebuffer console visible rather than selecting release silence |
| `CHAINLOADING=0`, `ESP_STAGE2=0`, `J613_ESP_STAGE1=0` | Omit the filesystem-chainloading feature and embedded ESP target |
| `EXTRA_CFLAGS=-DNO_DISPLAY` | Use the source's NO_DISPLAY configuration guards; do not start DCP display configuration |
| `LOGO=` | Do not append a custom-logo payload |
| Rust `1.99.0`, target `aarch64-unknown-none-softfloat`, Cargo `--locked` | Match the selected package's Rust version while retaining the locked dependency graph |

The pinned [Makefile](https://github.com/aurora-silicon/aura/blob/553b566f69275ff4e46ee6542a7236fb80a333a2/Makefile)
does **not** translate a bare `NO_DISPLAY=1` make argument into a compiler define.
The wrapper verifies actual C compilation commands and the effective preprocessor
macros. It requires USE_FB and NO_DISPLAY and rejects release silence, chainloading,
Stage 2, BRINGUP, special J613, early interception and debug-USB configurations.

[display.c](https://github.com/aurora-silicon/aura/blob/553b566f69275ff4e46ee6542a7236fb80a333a2/src/display.c)
has the NO_DISPLAY guard in display configuration. The existing
[fb.c](https://github.com/aurora-silicon/aura/blob/553b566f69275ff4e46ee6542a7236fb80a333a2/src/fb.c)
uses the firmware-provided boot framebuffer. This avoids requesting a new display
mode; it does not prove the framebuffer is valid or that no hardware is touched.

The generated raw image must have the expected build tag, terminate at STACKBOT,
contain no embedded Stage-1 configuration block, and have AArch64 ELF entry offset
2048. A separate `UNQUALIFIED-stage1-proxy-REVIEW-ONLY.bin` contains the raw image
followed only by a four-byte-or-longer zero terminator and zero padding to a
64 KiB boundary. This matches the reviewed installer's
[empty-variable construction](https://github.com/GravityLinux/installer/blob/6420623289fe7544cb8589b658355e57f0290fcc/src/m1n1.py).
No enrollment command or existing boot object is used as an input.

That layout prevents an unintended appended payload; it is not an Apple
personalization, enrollment or successful-boot verdict. The normal loader still
contains RAM-loading/proxy capabilities. Do not turn this file into an unattended
boot attempt or append a kernel because its build check passed.

## What the installer source says about the T7

The J713 downstream's documented installer is an internal-SSD installation.
Inspection of its Gravity installer base
`6420623289fe7544cb8589b658355e57f0290fcc` narrows the alternatives:

- [main.py](https://github.com/GravityLinux/installer/blob/6420623289fe7544cb8589b658355e57f0290fcc/src/main.py)
  has an external-disk selection path in expert mode. `choose_os` filters external
  choices to templates explicitly marked `external_boot`; this is code support,
  not a qualified J713/T7 profile.
- `action_install_into_free` creates the stub on the selected disk, and
  [OSInstaller.partition_disk](https://github.com/GravityLinux/installer/blob/6420623289fe7544cb8589b658355e57f0290fcc/src/osinstall.py)
  adds each OS partition after that stub. The reviewed flow does not have an
  independent internal-stub/external-root target selector.
- The stub-size constant is `align_down(2.5GB, 1MiB)`. A monitor-only template with
  no OS partitions is a **development proposal**, not a published qualified J713
  installation profile. We have not run or generated such an installer.
- The [paired-Recovery step](https://github.com/GravityLinux/installer/blob/6420623289fe7544cb8589b658355e57f0290fcc/src/step2/step2.sh)
  checks the specific new OS identity and 1TR mode before authorization. Its
  external-volume branch explicitly copies recovery authorization data into
  internal iSCPreboot. Thus, even selecting an external disk is not a promise of
  zero internal writes.

A minimal internal boot stub plus a later T7 rootfs is worth developing, but it
would require separate approval for concrete internal changes. A T7-hosted stub
also requires actual J713 boot/pairing qualification and still uses internal boot
metadata. Neither path is ready to execute from the current evidence.

## Firmware, handoff and recovery limits

The currently running macOS boot context is separate from the downstream profile's
26.5.1 / 25F80 OS-paired firmware. Our current system's firmware string is absent
from the selected Aura table. This profile neither adds a guessed firmware entry
nor proves future paired-firmware compatibility on the newer host/system state.

The downstream [J713 ANS reset investigation](https://github.com/Kb2uka/Omarchy-M4-Native/blob/7d107f95bff1bc32efb2dd0fd019f9f4c1dba6a3/docs/j713-m1n1-issue82-ans-reset.md)
reports real boot hangs and a stage-1 fix on its older m1n1 stack. Do not apply that
patch blindly: our pinned Aura already has a different T8132 shutdown/adoption
path. The proxy-only object has no configured filesystem payload to initiate that
chainload path; this is not qualification of its later NVMe/Linux handoff.

Before a native attempt, review together: an expendable OS/stub identity; the exact
installer and paired firmware; all disk/boot-policy writes; visible output; a
bounded attended test; owner authentication; return through startup options; and
available recovery resources. The loader disables the watchdog during normal
initialization, so automatic return must not be assumed. Recovery-host access is
still not a demonstrated recovery. The current build script cannot perform any
of those steps and asks for no credentials.

## What to do now

Review the PR after **Stage-1 proxy-only build** passes, then mark ready and merge
when satisfied. No new Mac/T7 action, file installation or kernel rebuild is
requested. CI uploads reports, configuration and build logs only. It intentionally
does not distribute an installable upstream binary without its source bundle.

Optional reproduction on an equipped Linux build host:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/stage1_proxy.py --llvm-dir /path/to/llvm/bin
```

The host needs git, GNU make, clang/LLVM/LLD, and the already installed Rust 1.99.0
bare-metal target. The script downloads exact source and locked dependencies and
writes only under ignored `work/stage1-proxy/`. It does not install dependencies,
execute installer/proxy clients or access devices. The CI workflow provisions its
own disposable build tools. Build acceptance is `STAGE1_PROXY_BUILD_ONLY_PASS`;
native entry and native boot flags remain false.
