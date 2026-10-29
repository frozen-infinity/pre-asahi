# Read-only recovery check on the borrowed Mac

This folder is for a **file inspection**, not for installing Linux, changing
startup security, entering DFU, reviving/restoring either Mac or formatting a disk.
The second Mac is otherwise only a standby recovery host for the later native
experiment. Merely having it available does not mean a revive is expected.

The 25F80 recovery image matches its pinned decoded SHA-256 and passed Apple
image verification on the M4. Its read-only mounted content reads stalled there.
Those task processes were stopped and the image was ejected. We need an independent
inspection result; no repeat mount on the original M4 is requested.

## Transfer and run

1. Copy the complete `recovery-check-for-second-mac` folder to the borrowed Mac's
   ordinary writable local storage. The existing T7 filesystem can carry these
   files; it does not need formatting. Keep the 1,560,927,608-byte `BaseSystem.dmg`
   beside `inspect_recovery.py`. Do not open the DMG in Finder first.
2. On the borrowed Mac, use a working Python **3.9 or later**. The checker uses
   only the standard library and installs nothing. If Python is unavailable,
   stop and report that; do not accept unrelated tool-installation prompts.
3. Open Terminal in that copied folder. Verify the transferred file first:

   ```sh
   python3 inspect_recovery.py
   ```

   Expected: `TRANSFERRED_RECOVERY_HASH_ONLY_PASS`. This step does not mount the
   image and can also be used to check a file transfer before borrowing the Mac.
4. On the **borrowed Mac**, run the content check once:

   ```sh
   python3 inspect_recovery.py --inspect
   ```

   Do not use sudo. The script checks the exact image hash, refuses a pre-existing
   attachment, attaches read-only without opening Finder, and reads version/tool
   presence in a child limited to 30 seconds. It never executes a binary from the
   image. It then ejects only the virtual device associated with that exact DMG.
   It does not select, format or eject the T7 or another physical disk.
5. Send the generated `inspection-*.json` report. It contains the host macOS
   version/architecture, image hash, inspection outcome, tool-relative paths and
   cleanup result. No serials, UUIDs, disk identifiers, volume names, raw system
   inventory or credentials are retained.

`RECOVERY_CONTENT_INSPECTION_ONLY_PASS` requires both the expected 26.5.1/25F80
contents and confirmed image cleanup. It is not proof of Apple personalization,
external-stub enrollment, native Linux boot, or DFU recovery on this M4.

If a stage times out or returns an error, let the checker finish its cleanup and
retain the report. Do not keep retrying. `RECOVERY_INSPECTION_CLEANUP_UNCONFIRMED`
means the script could not confirm ejection. In Disk Utility, identify this
`BaseSystem.dmg` disk image and eject that image; do not erase or eject a physical
disk. Report the failure before taking another step. The script never escalates
to force-ejecting a device.

The image is Apple restore material staged privately for this check; it is not
distributed in the GitHub PR or CI artifacts. A local hard link may have been
used when preparing this folder to save space. Copying the folder to the other
Mac makes an ordinary independent file. Do not edit the image in either copy.

## Current validation

The prepared local image's full size/hash and portable hash-only command were
checked. Unit tests exercise success, child timeout, cleanup failure, existing
attachment refusal and wrong-file refusal with substitutes. CI runs these
portable tests only, not an Apple-image mount. The actual borrowed-Mac result
is still needed; no second-Mac test is claimed yet.
