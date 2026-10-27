#!/bin/bash
# Runs only inside the disposable ARM Linux container created by candidate_build.py.
set -euo pipefail
[[ $(uname -m) == aarch64 && $# == 2 && $2 =~ ^[0-9a-f]{40}$ ]]
component=$1
commit=$2
case "$component" in
  aura) package=aura; source_name=aura; source_url=https://github.com/aurora-silicon/aura.git ;;
  kernel-config|kernel) package=linux-aurora; source_name=linux; source_url=https://github.com/aurora-silicon/linux.git ;;
  *) exit 2 ;;
esac

# These package changes affect the disposable container filesystem only.
pacman-key --init
pacman-key --populate archlinuxarm
pacman -Syu --noconfirm --needed base-devel git python clang llvm lld rustup make \
  bc dtc kmod libelf pahole cpio perl tar xz xmlto
useradd --create-home builder
mkdir -p /build/recipe /build/source-cache /build/pkgdest
cp -a /recipe-input/. /build/recipe/
cp /etc/makepkg.conf /build/makepkg.conf
cat >> /build/makepkg.conf <<'CONFIG'
SRCDEST=/build/source-cache
PKGDEST=/build/pkgdest
MAKEFLAGS=-j4
CONFIG
chown -R builder:builder /build

# Preseed a shallow source mirror. --holdver prevents makepkg updating it.
runuser -u builder -- git init --bare "/build/source-cache/$source_name"
runuser -u builder -- git -C "/build/source-cache/$source_name" remote add origin "$source_url"
runuser -u builder -- git -C "/build/source-cache/$source_name" fetch --depth=1 --no-tags origin "$commit:refs/heads/pinned"
runuser -u builder -- git -C "/build/source-cache/$source_name" symbolic-ref HEAD refs/heads/pinned

cd /build/recipe
if [[ $component == aura ]]; then
  runuser -u builder -- env HOME=/home/builder OMARCHY_BUILD_JOBS=4 \
    makepkg --config /build/makepkg.conf --holdver --noconfirm --cleanbuild --nosign
  # Accompany distributable GPL components with the complete makepkg source archive.
  runuser -u builder -- env HOME=/home/builder \
    makepkg --config /build/makepkg.conf --holdver --allsource --nosign
  mkdir -p /output/packages /output/sources
  shopt -s nullglob
  packages=(/build/pkgdest/*.pkg.tar.*)
  sources=(/build/recipe/*.src.tar.*)
  (( ${#packages[@]} > 0 && ${#sources[@]} > 0 ))
  cp "${packages[@]}" /output/packages/
  cp "${sources[@]}" /output/sources/
else
  # prepare() resolves/validates the paired configuration and generates headers.
  # The configuration-only mode stops here. Full mode calls the pinned build().
  runuser -u builder -- env HOME=/home/builder OMARCHY_BUILD_JOBS=4 \
    makepkg --config /build/makepkg.conf --holdver --noconfirm --nobuild
  config=/build/recipe/src/linux/build/base/.config
  grep -qx 'CONFIG_RUST=y' "$config"
  grep -qx 'CONFIG_ARM64_16K_PAGES=y' "$config"
  mkdir -p /output/kernel-config
  cp "$config" /output/kernel-config/resolved.config
  cp /build/recipe/src/linux/build/base/version /output/kernel-config/kernelrelease.txt
  if [[ $component == kernel ]]; then
    # Reuse the recipe's _make, toolchain and build() rather than duplicating flags.
    # package() and install hooks are deliberately never invoked.
    runuser -u builder -- env HOME=/home/builder OMARCHY_BUILD_JOBS=4 bash -euo pipefail <<'KERNEL_BUILD'
export srcdir="$PWD/src"
source ./PKGBUILD
# makepkg calls build() from srcdir; the recipe itself enters linux from there.
cd "$srcdir"
build
KERNEL_BUILD
    cd /build/recipe/src/linux
    test -s build/base/arch/arm64/boot/Image
    test -s build/base/arch/arm64/boot/dts/apple/t8132-j713.dtb
    test -s build/base/modules.order
    mkdir -p /output/kernel/dtbs /output/sources
    cp build/base/arch/arm64/boot/Image /output/kernel/
    cp build/base/arch/arm64/boot/dts/apple/*.dtb /output/kernel/dtbs/
    cp build/base/Module.symvers build/base/modules.order build/base/System.map /output/kernel/
    find build/base -type f -name '*.ko' -print0 > /build/modules.list
    test -s /build/modules.list
    tar --null --files-from=/build/modules.list --zstd -cf /output/kernel/modules.tar.zst
    # Retain the exact tracked sources plus all recipe/config inputs alongside binaries.
    runuser -u builder -- git archive --format=tar "$commit" | gzip -1 > /output/sources/linux-source.tar.gz
    tar -C /recipe-input -czf /output/sources/kernel-recipe.tar.gz .
  fi
fi
[[ $(runuser -u builder -- git -C "/build/recipe/src/$source_name" rev-parse HEAD) == "$commit" ]]
pacman -Q > /output/container-packages.txt
runuser -u builder -- env HOME=/home/builder rustup run 1.99.0 rustc --version > /output/rust-version.txt
python - "$component" "$commit" <<'PY'
import json, pathlib, sys
pathlib.Path('/output/component-result.json').write_text(json.dumps({
    'component': sys.argv[1], 'source_commit': sys.argv[2],
    'status': {'aura': 'AURA_PACKAGE_BUILT', 'kernel-config': 'KERNEL_CONFIG_PREPARED',
               'kernel': 'FULL_KERNEL_BUILT_QEMU_PENDING'}[sys.argv[1]],
    'full_kernel_built': sys.argv[1] == 'kernel', 'native_boot_proven': False,
    'installation_qualified': False}, indent=2) + '\n')
PY
