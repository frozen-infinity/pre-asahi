# Build pinned m1n1 with Arch-managed Rust

The user's j713 kernel Image.gz and DTB were produced on the Arch build host; the reported DTB compatible list matches j713/t8132. This is user-reported build/artifact evidence, not independently reproduced hardware execution. Keep the full kernel log, source lock, .config, compiler metadata and manifest locally. Raw reports and identifiers are not committed.

The reported Rust is Arch-managed (`/usr/bin/rustc`, `/usr/bin/cargo`) without rustup. Do not replace it just to obtain m1n1's bare-metal target. At pinned m1n1 revision `51b747dced07a58eacf5dabc31ed6f00bcfa20fd`, the [Makefile](https://github.com/AsahiLinux/m1n1/blob/51b747dced07a58eacf5dabc31ed6f00bcfa20fd/Makefile) supports `BUILDSTD=1`, sets `RUSTC_BOOTSTRAP=1` in the upstream build, and requests Cargo to build `alloc,core` for `aarch64-unknown-none-softfloat`. It also includes an LLVM workaround; retain the pinned Makefile unchanged.

This is an upstream-provided experimental build option, not a guarantee that every stable Rust release works. Cargo's build-std path is unstable. Arch's [rust-src package](https://archlinux.org/packages/extra/x86_64/rust-src/) supplies Rust library source. The installed package/source/compiler must match; stale mirrors or mixed toolchains can fail. No Rust version is pinned or claimed compatible by this guide.

## 1. Preserve kernel evidence

From the existing pre-asahi directory on the Arch laptop:

```sh
cp -n reports/manifest.json reports/kernel-manifest.json
```

If the destination exists, keep it; do not overwrite earlier evidence accidentally. Keep sources.lock.json and work/src unchanged. These commands use the existing preparation scripts; switching branches is not required to try this documented build option.

## 2. Install matching Rust sources on the Arch laptop

Review the transaction; this performs a normal full Arch upgrade and can update the compiler. It does not operate on the Mac or T7. Do not use a partial upgrade or force an old rust-src package.

```sh
sudo pacman -Syu --needed rust-src
pacman -Q rust rust-src
rustc --version
cargo --version
command -v rustc
command -v cargo
```

Both rust and rust-src should report the same Arch package version. Stop if they differ or the active compiler/cargo comes from a different installation. Expected for this route: /usr/bin/rustc and /usr/bin/cargo. If the compiler changed, retain its new version in the m1n1 evidence; do not claim an earlier kernel was built with it.

In Bash, verify the source location used by the active compiler:

```sh
rust_source="$(rustc --print sysroot)/lib/rustlib/src/rust/library"
if test -r "$rust_source/core/Cargo.toml" && test -r "$rust_source/alloc/Cargo.toml"; then
    echo "Rust core/alloc sources found"
else
    echo "STOP: matching Rust library sources are missing"
fi
```

Do not continue on the STOP message. Checking source files is a prerequisite, not proof Cargo will build them successfully.

## 3. Compile locally, without booting

In Bash, from pre-asahi after the checks pass:

```sh
mkdir -p reports
set -o pipefail
BUILDSTD=1 python3 scripts/bringup.py build-m1n1 2>&1 | tee reports/m1n1-build.log
result=$?
echo "Build exit status: $result"
```

The environment setting is passed through the existing Python wrapper to upstream make. It is scoped to this invocation; do not export RUSTC_BOOTSTRAP globally or edit upstream sources. Cargo may download dependencies into its normal user cache. No root access is needed for compilation. The wrapper verifies the source revision, tracked source cleanliness, submodule revision and output presence.

On failure, retain the first compiler/Cargo error and surrounding lines. Do not delete source locks, switch compiler versions blindly, or remove upstream LLVM flags to force progress.

On success:

```sh
ls -lh work/src/m1n1/build/m1n1.bin work/src/m1n1/build/m1n1.macho
python3 scripts/bringup.py manifest
```

Send the package/compiler versions, source-check result, build exit status and either output sizes/manifest or the first error. A future improvement should record complete bootloader dependency/toolchain metadata automatically; the current manifest only hashes available artifacts and does not prove reproducibility.

This creates bootloader build artifacts only. No payload is installed, no boot entry is provisioned, and no security setting or disk partition is changed. Keep the T7 and Mac disconnected. Native boot, firmware compatibility, transport and diagnostic initramfs gates remain open.

## Validation

Inspected the pinned upstream Makefile and Cargo manifest. Shell examples passed Bash syntax checks; no Arch package installation, Rust build-std compilation or m1n1 build was run in the macOS development session. Actual compatibility with the user's Arch packages remains to be tested. No upstream contribution was made.
