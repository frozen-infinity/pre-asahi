# Intel Arch Linux build host

This is cross compilation on x86_64, not an Arch Linux ARM installation. Use the Arch laptop's existing Linux filesystem for sources/builds. The T7 may remain disconnected. The user's target is j713; use `--model j713`, not j715. No device identifiers or user reports are committed here.

## 1. Install development dependencies

Review the package transaction. This updates the Arch laptop and installs build dependencies; it does not touch the Mac or T7. Arch requires a full upgrade rather than a partial upgrade.

```sh
sudo pacman -Syu --needed base-devel git python aarch64-linux-gnu-gcc aarch64-linux-gnu-binutils dtc bc openssl libelf imagemagick clang llvm lld
```

[AArch64 GCC is in Arch's official Extra repository](https://archlinux.org/packages/extra/x86_64/aarch64-linux-gnu-gcc/) and depends on its matching cross-binutils. No AUR helper is required. Installed versions may differ from the upstream tested combination; record failures rather than forcing a build through them.

## 2. Check the cross compiler

If this is a new clone:

```sh
git clone --branch arch-host-build https://github.com/frozen-infinity/pre-asahi.git
cd pre-asahi
```

For an existing clone, first inspect `git status`; retain any local changes. Then `git fetch origin` and `git switch arch-host-build` (or `git switch --track origin/arch-host-build` when no local branch exists). After this PR merges, use main instead.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_cross.py
```

The new check compiles a small object, checks its ELF type/architecture, and records compiler metadata in `reports/cross-toolchain.json`. It does not run the AArch64 object. Existing x86_64 GCC cannot substitute for an AArch64 compiler. A passing result proves only a basic cross-compilation operation, not compatibility with this kernel revision.

## 3. Fetch, inspect, then build the kernel

```sh
python3 scripts/bringup.py fetch
cat sources.lock.json
```

This resolves upstream branches once and downloads pinned sources plus m1n1 submodules. Linux source can take substantial space; check free space first. Review the exact checked-out source/config and upstream build instructions before invoking builds. Keep the generated lock with the build evidence; do not silently re-resolve it between runs. The current fetch command obtains both repositories even if you build only Linux.

When ready to run the source build, in Bash:

```sh
mkdir -p reports
set -o pipefail
python3 scripts/bringup.py build-linux --model j713 2>&1 | tee reports/kernel-build.log
```

Stop at the first error. Do not install a host kernel, run an installer, copy files into a boot partition, or attach the Mac for these steps. On success inspect `work/build/j713/arch/arm64/boot/Image.gz`, `work/build/j713/arch/arm64/boot/dts/apple/t8132-j713.dtb` and the resolved `.config`. Run `python3 scripts/bringup.py manifest` to hash available artifacts. The manifest can be partial and is not a readiness verdict.

Send the cross-toolchain result, source lock and build exit/result in the chat. For a failure send the first actual error plus surrounding lines, not just the final make failure. Review logs for private paths before sharing.

## m1n1 Rust setup is a separate gate

Do not infer that `/usr/bin/rustc` and `/usr/bin/cargo` provide m1n1's bare-metal target. [Upstream m1n1](https://github.com/AsahiLinux/m1n1#building) requires `aarch64-unknown-none-softfloat`. Before changing Rust packages, report:

```sh
rustc --version
cargo --version
command -v rustup || true
rustc --print target-libdir --target aarch64-unknown-none-softfloat
```

The last command may print a directory even when its libraries are absent. It alone is not target validation. If using rustup already, `rustup target list --installed` gives useful additional evidence. Do not overwrite a distro-managed Rust setup or mix its cargo with a rustup compiler blindly. Kernel preparation can proceed separately; the bare-metal Rust toolchain will be selected using the exact locked m1n1 requirements.

## Validation limits

The guide and Python syntax were checked in the macOS development session. The two existing scaffold tests passed. There is no Arch package transaction, GCC cross compilation or upstream kernel build result from this session. These are the next checks for the user's Arch host. All native boot, firmware compatibility and USB/T7 gates remain open.
