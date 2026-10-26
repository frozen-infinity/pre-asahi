# Build the diagnostic initramfs on the Intel Arch host

The user has reported successful j713 kernel/DTB and m1n1 builds, with artifact hashes. This step adds minimal static AArch64 userspace. It does not install an OS or boot the Mac. Keep the T7 and Mac disconnected.

## Prepare

On the Arch laptop, inside a clean pre-asahi checkout (retain any local changes first):

```sh
git fetch origin
git switch --track origin/diagnostic-initramfs
sudo pacman -Syu --needed curl cpio qemu-user
python3 -m unittest discover -s tests -v
```

If the local branch exists already, use `git switch diagnostic-initramfs`. This branch is based on main; it does not change or rebuild the existing kernel, m1n1 or source lock. Retain the existing kernel logs/config and manifest. The build does not need a newly configured kernel.

`qemu-user` provides the explicit `qemu-aarch64` command; no binfmt setup is required. QEMU user mode runs AArch64 userspace against the host kernel. It does not emulate the M4 or boot a Linux kernel. Only the applet-list and a harmless shell/test/echo check run under QEMU here; never execute `/init` on the development host.

## Download and build

The pinned source is BusyBox 1.38.0 from its [upstream download directory](https://www.busybox.net/downloads/). SHA-256 is cross-checked against [Buildroot's source-hash record](https://github.com/buildroot/buildroot/blob/master/package/busybox/busybox.hash). A hash pin detects different bytes; it is not independent signature verification. The builder checks the fixed hash before extraction, rejects paths outside the versioned source root and links/special entries, then compiles the reviewed source. The source archive is kept for reproducibility and license compliance.

```sh
mkdir -p work/downloads reports
curl --fail --location --proto '=https' --tlsv1.2 \
  https://www.busybox.net/downloads/busybox-1.38.0.tar.bz2 \
  -o work/downloads/busybox-1.38.0.tar.bz2
```

In Bash, after the download succeeds:

```sh
set -o pipefail
python3 scripts/build_busybox.py --archive work/downloads/busybox-1.38.0.tar.bz2 2>&1 | tee reports/busybox-build.log
result=$?
echo "Build exit status: $result"
```

The script uses the existing aarch64-linux-gnu GCC compiler and static target libc. It creates a fresh `work/busybox-attempt-*` source/build tree for every attempt, retaining failed attempts for debugging instead of reusing modified source. Keep enough free space; nothing is automatically removed. It first creates an all-disabled base, overlays configs/busybox.config, and resolves with upstream defconfig. All requested settings must survive. BusyBox allnoconfig alone would reset the fragment's booleans, so this resolution step matters.

Required applets are sh, mount, uname, tr, sleep. Ash supplies echo and the `test`/`[` builtin. All other optional commands start disabled, subject to Kconfig's required defaults/dependencies. No networking, disk partitioning tools or persistent root filesystem is needed. Static ELF architecture/type checks and both explicit QEMU checks must pass before the script copies outputs and creates the cpio archive. The binary is built from source; no precompiled BusyBox is downloaded. Treat GCC/libc compatibility as untested until the actual build passes; retain the first compiler error if it fails.

## Inspect the results after exit status 0

```sh
ls -lh work/artifacts/busybox work/artifacts/initramfs.cpio.gz
cat work/artifacts/busybox-build.json
set -o pipefail
gzip -dc work/artifacts/initramfs.cpio.gz | cpio -itv
python3 scripts/bringup.py manifest
cat reports/manifest.json
```

The archive listing should include bin/busybox, executable init, dev/console (character device 5,1), and bin/dev/proc/sys/tmp directories. Listing does not extract anything or create device nodes on the host. `/init` mounts only proc, sysfs and devtmpfs, prints `M4AIR_PHASE1_PID1`, reports kernel/compatible, and sleeps. The marker is only a future on-target acceptance condition. The QEMU test prints the distinct marker `BUSYBOX_AARCH64_OK`; it is not native PID 1 proof.

Send the exit status, busybox-build.json, archive listing and manifest. For failure, send the first error and surrounding lines. Review private paths before sharing. Stop on failure even if artifacts from an older successful attempt still exist. A manifest may contain partial or old artifacts; it is not a build-success signal.

Do not concatenate payloads, install a boot entry, use recovery commands, or copy artifacts to a boot partition. Boot provisioning, exact firmware compatibility, logging transport and return-to-macOS remain separate unresolved gates. No T7 formatting is needed. Before distributing a BusyBox binary, retain its GPL source/config and comply with the upstream LICENSE; this repository publishes no compiled binaries.

## Validation of this PR

Downloaded BusyBox 1.38.0 and matched SHA-256 `34f9ea6ff8636f2c9241153b9114eefa9e65674a45318ae1ef95bb5f31c53bb2`. Upstream Kconfig ran locally on macOS with Clang for its host tools, and all nine requested config values resolved correctly. Four Python tests passed, covering ELF gating, cpio structure and rejecting unsafe archive entries. Documented shell blocks passed Bash syntax checks. No AArch64 BusyBox compilation, QEMU userspace test or hardware boot was performed in this macOS session; these are the next Arch-host checks.
