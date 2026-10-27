# Production J713 importer tested with synthetic trees

The [pinned U-Boot suite](https://github.com/aurora-silicon/u-boot/blob/7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c/test/py/tests/test_apple_j713_fdt.py)
already provides synthetic fixtures that compile the production J713 importer
and libfdt for the development host. This runner uses that unmodified suite
instead of implementing a second importer or copying its logic into a test.

## Verified locally

The actual pinned source compiled with Apple clang 21.0.0 and DTC 1.8.1 on macOS.
All **56 synthetic importer invocations** and **five padding compile checks**
passed, across four upstream test groups:

| Group | What is exercised |
| --- | --- |
| Runtime import | Graphics/basic targets; runtime references and destination phandles; rejected or legacy handoffs; reserved memory and policy preservation |
| Peripheral calibration | Synthetic Bluetooth/ATC data, malformed or missing properties and failure rollback |
| Optional multifunction calibration | Missing versus malformed AUX/calibration data and selective degradation |
| Padding guard | Compiler acceptance/rejection around the required 144 KiB padding threshold |

The upstream test faults include wrong model identity, insufficient capacity,
malformed source markers, invalid references and optional device admission.
Successful imports check repeatability and translated references; rejected
imports check that destination bytes remain unchanged where required. A source
marker or completed import is not evidence of live MTP or firmware readiness.

Result: **SYNTHETIC_IMPORTER_PASS**. This executes production DT manipulation on
the host, not Apple firmware or hardware helper code. It does not use the saved
kernel DTB as the OS fixture. The trees contain invented data, not a capture of
this Mac. The prior saved-artifact and emulator checks remain separate evidence.

## Inputs and execution boundary

`configs/j713-fixtures.lock.json` pins 15 individual files from the same U-Boot
commit as the successful package build: importer, header, upstream tests and
the libfdt source/header subset used by its host harness. Every file must match
its SHA-256 before any upstream Python is imported or any C compilation starts.
Only missing files may be downloaded; changed cached files fail instead of being
silently refreshed. Upstream code stays under ignored `work/`, with its license
headers intact; it is not vendored into this repository.

The runner calls only the four synthetic groups. It clears private-capture
environment variables and does not call the upstream private-capture test. It
does not load hardware DTBs, device identifiers, USB connections or firmware.
The worker and its compiler/test descendants have a three-minute timeout.

Reports use a fresh ignored `reports/j713-fixtures-*` directory and include
source hashes, compiler/DTC versions, test groups and explicit synthetic/native
status. Logs and test-generated files stay local; the workflow uploads only the
report and host log. No test result is a hardware boot authorization.

## User steps after merge

The local test already passed; no kernel or U-Boot rebuild is needed. For an
independent Linux reproduction:

1. Open **Actions → J713 handoff fixtures → Run workflow** on **main**.
2. Share the run link. This is a short host test on an x86 Linux runner, not the
   full ARM kernel build.

Alternatively, with `cc`, `dtc` and Python 3.9+ already installed on a development
host, run `python3 scripts/j713_fixtures.py --fetch`. This executes the pinned
upstream host suite locally. After the cache exists, omit `--fetch` for offline
verification. Nothing installs dependencies automatically outside the disposable
CI runner. No Mac/T7 boot or storage changes are requested.

## Next integration gate

Synthetic success establishes that the selected importer's tested contracts hold
for these fixtures. It cannot show that Aura on this Mac supplies equivalent
runtime state, that the saved kernel DTB has every required path/marker, or that
firmware addresses are safe. Before generating a bundle, check the saved DTB's
static opt-in, required topology and buffer contract against this exact importer,
and keep actual runtime admission unresolved until evidence exists. Native
entry, logging and recovery remain required before any hardware attempt.
