# Local validation — 2026-10-25

Completed:
- Python CLI help and read-only diagnostics executed on this macOS development session.
- Two unit tests passed: static AArch64 ELF gate rejects wrong architecture/dynamic executables; deterministic newc archive parsing checks file contents, permissions, character-device major/minor, alignment and trailer.
- Linux build refuses macOS with an explicit Linux-host requirement.
- Diagnostic report explicitly records unavailable hardware identity instead of guessing.

Not completed:
- Git source resolution/download: attempted public GitHub reads failed DNS resolution in this session. There is no sources.lock.json yet. The fetch command creates it on a network-enabled development host.
- m1n1 and kernel compilation: not attempted without sources and required toolchains. LLVM lld/objcopy and the AArch64 GCC cross compiler were not found on PATH; this does not rule out installations elsewhere.
- Real BusyBox archive: no reviewed static AArch64 BusyBox supplied; unit tests use structural fixtures, not a functioning executable. ELF validation alone cannot establish BusyBox applet availability or runtime behavior. Required applets: sh, mount, uname, tr, sleep; echo may be a shell builtin.
- Exact target model/firmware, boot transport, cold starts, native kernel boot and Arch userspace: unverified.

Status: scaffold ready for source review and build-host preparation. No bootable image or completed hardware milestone is claimed. No disk layout, boot policy, firmware or installed OS was changed.

Repository publication update: README now includes PR-based development, copyable macOS checks, and the separate T7 plan. No T7 was inspected, mounted, formatted, partitioned, or used for a boot test. Local generated reports remain excluded from the proposed commit.
