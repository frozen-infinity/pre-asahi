# Real Linux EFI consumer on QEMU

The [publication test](efi-publication-test.md) passed in [CI](https://github.com/frozen-infinity/pre-asahi/actions/runs/40658293937).
This step connects publication to a real Linux EFI stub and a RAM-only PID 1.
It does not change any upstream source pins or build another kernel.

## Test chain

1. Download the exact saved kernel artifact from run `40468038656`, artifact
   `12719093458`. Verify its byte count and ZIP SHA-256 from `artifact-set.json`
   before reading payloads. Check kernel/config hashes, source receipts, 16 KiB
   Image header, EFI PE header and required configuration.
2. Build the same selected U-Boot source's generic QEMU target. Require the prior
   APPLY and temporary publication/restoration checks to pass first.
3. Generate a full QEMU virt DTB, never an Apple DTB. Keep one control copy with
   an unpublished cookie and another with a fresh random cookie for this run.
   Cross-compile a static AArch64 init and build its tiny initramfs.
4. Start a fresh diskless QEMU. Preload the launcher, exact kernel, initramfs and
   control DTB into separate fixed RAM ranges. U-Boot's `bootefi` exposes the
   initramfs via its real EFI LoadFile2 service and installs the control DTB.
5. The positive EFI app copies the private full DTB into pool memory and requests
   APPLY | INSTALL through the real DT Fixup protocol. It invokes EFI LoadImage
   on the kernel and StartImage with serial/init command-line options. The kernel
   handles ExitBootServices; the launcher must never return on success.
6. PID 1 mounts proc/sysfs, checks AArch64 and the 64-bit EFI firmware interface,
   then reads the cookie from Linux's live device-tree sysfs view. Only an exact
   fresh-cookie match prints the positive pass marker.

The negative control uses the same kernel/initramfs and launcher source, with
publication disabled. It must actually reach Linux PID 1 through EFI and reject
the original DTB. A timeout, failed launch or panic is not an accepted negative.
The positive must separately pass. Each guest is terminated by the host after two
seconds of accepted evidence; no reboot, storage or network action is requested.

## Results and limits

Overall acceptance is `EMULATED_LINUX_EFI_CONSUMER_PASS`. The report binds source,
generated headers, kernel, config, firmware, DTBs, initramfs, applications and
console hashes; it records positive and control results separately. This is an
acceptance criterion until the PR's CI run passes.

This tests a real kernel EFI consumer on generic QEMU, including the published
FDT, initrd service and exit from boot services. It does not test Apple firmware,
Aura, J713 board hooks, M4 interrupt/CPU drivers or native entry/recovery. Fixed
addresses and generated trees are QEMU test inputs, not hardware boot artifacts.
The published pool buffer remains alive during Linux handoff. If StartImage
returns, the app fails and attempts unload/restoration; it never frees a buffer
that might remain published or referenced by an image that failed to unload.

The archive is about 807 MiB. CI downloads it for verification, without rebuilding
or republishing the kernel. If the exact artifact expires, the check must fail;
it must not silently select a newer artifact. A previously saved byte-identical
ZIP can still be used locally. Downloaded source/build trees, kernel and initramfs
are excluded from this workflow's uploaded evidence.

## Your steps

1. Review the PR after **Linux EFI consumer on QEMU** and the existing
   **Selected-source U-Boot EFI probe** checks pass; mark ready and merge when
   satisfied. Both run automatically for the relevant changes.
2. No new download, Mac startup action or T7 preparation is needed.
3. Optional reproduction on an equipped x86_64 Linux cross-build host:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/uboot_efi_probe.py --linux-kernel-zip /path/to/UNQUALIFIED-candidate-kernel.zip
```

Dependencies are listed in `.github/workflows/linux-efi.yml`. In addition to the
previous EFI tools, the guest init needs the AArch64 static libc development
package. Source pins remain U-Boot `7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`
and Linux `311471f73e9919764bfb24acfe7eeb7c5230795a`; the kernel Image SHA-256 is
`1a16c332d3e807e668e21b1eae1e9bc5254bf87cc4bd7f0fef0af63329c2709f`.
