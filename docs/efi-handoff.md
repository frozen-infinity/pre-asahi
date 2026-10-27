# Loader selection and EFI DT publication

The next host test connects the saved OS DTB to the pinned U-Boot EFI fixup
implementation and its actual J713 board-hook logic. It passed on the development
Mac with **mock EFI services, a mock image-setup adapter and a mock RTKit helper**.
It is not execution inside a real EFI environment or native firmware admission.

## Two device-tree roles

The [pinned Apple board flow](https://github.com/aurora-silicon/u-boot/blob/7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c/arch/arm/mach-apple/board.c)
loads the removable-media EFI filename from its internal ESP and invokes the EFI
loader with `fdtcontroladdr`, its live runtime tree. This is distinct from our
separately selected, opt-in **OS DTB**, whose static topology comes from the saved
kernel. A caller introducing that OS DTB must request the appropriate fixup and
publication path; merely placing a DTB beside an EFI file does not select it.

The [ALARM image builder](https://github.com/aurora-silicon/alarm-aurora/blob/ac3b14d017cb5c316d21a8af3b3e38e40390b388/scripts/build-image)
installs GRUB for arm64 EFI. We have not built or run that GRUB/image integration,
and the saved archives do not provide a complete installed EFI environment.
This host probe tests the explicit OS-DTB fixup route, not automatic selection
of that DTB by GRUB or a UKI. No EFI executable is produced by the host probe.

The board defaults also suppress automatic USB startup/boot targets pending PHY
validation. A configured USB driver therefore does not establish a T7 boot path.
The separate external rootfs preference remains useful, but does not provision
the initial boot environment.

## Exact production pieces exercised

* The complete locked `lib/efi_loader/efi_dt_fixup.c` is compiled unchanged.
* The final `ft_board_setup()` definition is taken verbatim from locked `board.c`.
  The rest of that hardware board file is not compiled into this host test.
* The existing production J713 importer and pinned libfdt are compiled unchanged.
* `image_setup_libfdt()` is a host adapter calling that board hook; EFI memory-map,
  table-installation, environment/console and RTKit helper services are mocks.
  This is neither a complete U-Boot sandbox nor an EFI ABI/protocol-discovery test.

Two additional source files are pinned by SHA-256 in `configs/efi-handoff.lock.json`
at the same U-Boot commit. Existing importer/libfdt files retain their prior lock.
Every upstream source is verified before compilation or import. The extracted
board-hook suffix is generated in ignored workspace scratch and separately hashed.

## Observed sequence checks

| Case | Observed host result |
| --- | --- |
| Invalid protocol instance or zero flags | Invalid parameter; no board call/publication |
| Insufficient logical buffer | Buffer-too-small, requested capacity returned; no board/helper/reservation/publication and unchanged input |
| Invalid OS source identity | Rejected before helper, reservation or publication |
| Simulated helper refusal | Board fails; no completion marker, reservation or publication |
| Simulated helper success with APPLY/RESERVE/INSTALL | Actual board hook completes the imported DT; memory reservation mocks run and the table mock receives that exact tree |
| APPLY only | Fixups/helper run, but no reservation or table publication |

Successful processing also checks preserved static clock/power/pinctrl policy
and resolved memory-region references. The helper-refusal case can leave an
imported *working buffer* changed; the real EFI function does not publish it on
failure. The harness discards/rebuilds that buffer before retry. Only the importer
itself has the previously tested no-mutation-on-import-rejection guarantee.

Result: **HOST_EFI_SEQUENCE_PASS**. The original archives and prepared static DTB
remain unchanged. The table and memory reservations are counters/pointers in the
host process; they never touch a firmware table or real address range. The mock
helper's success cannot establish real coprocessor ownership or readiness.

## Reproduction after merge

The full saved-artifact/OS-DTB/EFI host chain already passed locally; no kernel
or U-Boot rebuild or new CI run is required. Optional reproduction:

```sh
python3 scripts/efi_handoff.py --fetch \
  --kernel "$HOME/Downloads/UNQUALIFIED-candidate-kernel-3.zip"
```

If necessary, populate the importer subset first with
`python3 scripts/j713_fixtures.py --fetch`. The EFI runner's fetch flag downloads
only its two extra locked files; it never replaces changed cache files. With all
sources cached, omit `--fetch`. Required tools remain Python 3.9+, `cc` and `dtc`.

Reports/logs appear beside the new `work/os-dtb-review-*` attempt. `result.json`
is the saved OS-tree/importer result; `efi-result.json` and `efi-host.log` describe
the additional mocked-service sequence. None should be committed.

## Next actual integration work

Update: [the standalone arm64 EFI discovery caller](efi-discovery-probe.md) now
builds and executes in QEMU/EDK2. It proves real EFI entry/console/protocol lookup
for the expected missing-protocol case, while DT allocation/Fixup and Linux
launch remain unimplemented. The work below is still required for that path.

The next executable must be a real arm64 EFI caller/boot manager that selects
the OS DTB, handles buffer negotiation and invokes the real protocol before OS
loading. It needs to detect missing protocol or refused helper state and stop
without starting Linux. These host results inform that implementation but do
not substitute for running it in a firmware environment. The actual Aura runtime
and model/firmware-specific first-entry/logging/recovery path remain required.
No saved synthetic tree, test release slot or mocked helper result may be used
to bypass those requirements. This PR performs no boot setup, storage write,
startup-security change or native boot.
