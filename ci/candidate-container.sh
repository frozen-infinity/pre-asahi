#!/bin/bash
# Runs only inside the disposable ARM Linux container created by candidate_build.py.
set -euo pipefail
[[ $(uname -m) == aarch64 && $# == 2 && $2 =~ ^[0-9a-f]{40}$ ]]
component=$1
commit=$2
case "$component" in
  aura) package=aura; source_name=aura; source_url=https://github.com/aurora-silicon/aura.git ;;
  kernel-config) package=linux-aurora; source_name=linux; source_url=https://github.com/aurora-silicon/linux.git ;;
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
  # This deliberately does not call the full kernel build() or package().
  runuser -u builder -- env HOME=/home/builder OMARCHY_BUILD_JOBS=4 \
    makepkg --config /build/makepkg.conf --holdver --noconfirm --nobuild
  config=/build/recipe/src/linux/build/base/.config
  grep -qx 'CONFIG_RUST=y' "$config"
  grep -qx 'CONFIG_ARM64_16K_PAGES=y' "$config"
  mkdir -p /output/kernel-config
  cp "$config" /output/kernel-config/resolved.config
  cp /build/recipe/src/linux/build/base/version /output/kernel-config/kernelrelease.txt
fi
[[ $(runuser -u builder -- git -C "/build/recipe/src/$source_name" rev-parse HEAD) == "$commit" ]]
pacman -Q > /output/container-packages.txt
runuser -u builder -- env HOME=/home/builder rustup run 1.99.0 rustc --version > /output/rust-version.txt
python - "$component" "$commit" <<'PY'
import json, pathlib, sys
pathlib.Path('/output/component-result.json').write_text(json.dumps({
    'component': sys.argv[1], 'source_commit': sys.argv[2],
    'status': 'AURA_PACKAGE_BUILT' if sys.argv[1] == 'aura' else 'KERNEL_CONFIG_PREPARED',
    'full_kernel_built': False, 'native_boot_proven': False,
    'installation_qualified': False}, indent=2) + '\n')
PY
