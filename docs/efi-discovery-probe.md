# Actual arm64 EFI discovery executable

`efi/probe.c` now builds as a standalone AArch64 PE32+ EFI application. The
actual executable ran under QEMU/EDK2 on the development Mac and reported:

```text
PRE_ASAHI_EFI_PROBE_STARTED
PRE_ASAHI_DT_FIXUP_ABSENT
PRE_ASAHI_NO_LINUX_LAUNCH
```

Result: **EMULATED_EFI_DISCOVERY_PASS_PROTOCOL_ABSENT**. EDK2 is not the selected
Apple U-Boot and does not supply its DT-fixup protocol, so absence is the expected
negative case. This establishes that the generated ARM64 EFI image was loaded,
its console and boot-services ABI worked in that firmware, and it handled missing
protocol support. It does not exercise a real U-Boot protocol, J713 hardware,
native first entry, DT fixups or Linux loading.

## What the executable does

The entry point validates the 64-bit system/boot table layout and signatures,
prints its startup marker, and calls `LocateProtocol` for the exact GUID used by
[the pinned U-Boot EFI API](https://github.com/aurora-silicon/u-boot/blob/7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c/include/efi_api.h):
`e617d64c-fe08-46da-f4dc-bbd5870c7300`. This must not be confused with other DT
protocols that have different GUIDs or function signatures.

If present, it checks a non-null Fixup entry and the selected protocol's revision
`0x10000`, then reports availability. It never calls Fixup. On missing/invalid
protocol or unsupported revision it reports the condition and returns an EFI
error. No code path loads another image, exits boot services, launches Linux,
writes a file, changes a variable or installs a configuration table. No machine
identifiers or firmware-memory addresses are printed.

The minimal table declarations follow the
[EDK2 UEFI system and boot-services layout](https://github.com/tianocore/edk2/blob/master/MdePkg/Include/Uefi/UefiSpec.h),
with compile-time offset checks. They are a small discovery-only interface, not
a replacement UEFI SDK for a future OS loader. Protocol presence is a prerequisite,
not proof that applying fixups or a hardware-helper handoff will succeed.

## Actual local validation

Built with Homebrew clang 22.1.6 and the already installed Rust toolchain's LLD
22.1.2 COFF linker. The PE header reports ARM64, PE32+, EFI application subsystem,
and no imported runtime libraries. The executable SHA-256 for this build was
`144d42cf7b7842192d4e851022a13478707800842d1d4669e7009493c3be72ad`.
Other compiler versions may produce different bytes; reports record their versions.

QEMU 11.0.1 with bundled EDK2 executed it under TCG in about six seconds. The
firmware code was read-only, its variable store was copied to a fresh ignored
workspace file, and the probe was exposed through a read-only virtual FAT
directory. The QEMU fallback filename exists only in that temporary virtual ESP.
No physical disk, USB device, network or Mac firmware variable was exposed.
QEMU was terminated after the expected markers were observed.

The same C entry point also passed host branch tests for absent/present protocol,
unsupported revision, missing function pointer, lookup failure and invalid system
table. The present-protocol test uses an intentionally uncallable Fixup sentinel,
so any accidental invocation would fail. These host tests remain distinct from
the actual EFI execution's missing-protocol result.

## Steps after merging

1. **Actions → ARM64 EFI discovery probe → Run workflow → main**.
2. Send the run link. This is a short cross-build/emulator job; it does not
   rebuild the kernel or U-Boot.

The workflow installs compiler/QEMU firmware packages only on its disposable
Ubuntu runner. It uploads the EFI executable, report and console log. The Linux
firmware package/toolchain combination still needs its first run; the local Mac
build/emulator path has passed already.

For local reproduction with the existing tools:

```sh
python3 scripts/efi_probe.py \
  --clang /opt/homebrew/opt/llvm/bin/clang \
  --linker "$(rustc --print sysroot)/lib/rustlib/aarch64-apple-darwin/bin/gcc-ld/lld-link" \
  --firmware-code /opt/homebrew/share/qemu/edk2-aarch64-code.fd \
  --firmware-vars /opt/homebrew/share/qemu/edk2-arm-vars.fd
```

The helper defaults to `qemu-system-aarch64` on PATH; pass `--qemu` if needed.
Omit both firmware arguments for build-only output. Each attempt gets a fresh
`work/efi-probe/attempt-*` directory containing the executable, PE object,
virtual boot directory, copied variable store, console log and result. Only the
EFI executable/report/log are CI outputs; generated firmware state is not uploaded.
Nothing is installed automatically on the Mac, and no boot configuration changes.

## Next integration gate

This is a real EFI discovery caller, not yet the OS-DTB Fixup caller. The next
step is executing it in an isolated test of the selected U-Boot EFI environment
and then implementing bounded DT input/allocation/Fixup error handling. The
previous mocked sequence remains useful for those ordering rules but is not an
execution result for that firmware. Native first entry and logging/recovery for
the Mac still must be established before loading the EFI probe on the actual
machine. No current result constitutes native boot proof.
