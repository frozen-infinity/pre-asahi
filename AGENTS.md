# Project working agreement

- Send code and documentation changes through PRs to frozen-infinity/pre-asahi. Do not push changes directly to main or merge PRs without the user's instruction.
- Keep README instructions current and repeat the immediate user steps in the chat when delivering a PR.
- Preserve the user's T7-first test-storage preference. No destructive disk changes, boot policy changes, or installer bypasses are authorized by that preference.
- Build toward native Linux RAM-only proof using existing Asahi infrastructure before Arch userspace or desktop drivers. Never present compile/emulator/hypervisor results as native hardware success.
- Record tested versus untested behavior, exact source revisions and material blockers. Review current upstream model/firmware support before proposing hardware execution.
- Do not commit reports, device identifiers, upstream trees, build artifacts, or user logs. Review generated archives before publication.
- Run `python3 -m unittest discover -s tests -v` for changes to the preparation scripts. Do not claim upstream builds passed unless they actually ran successfully.
- This project is AI-assisted. Respect upstream contribution and AI policies; no automatic upstream submissions.

## Current hardware preference

On 2026-10-27 the user explicitly clarified that necessary testing and running code on the Mac are authorized toward the final goal of native Linux on the M4. Do not keep the project artificially limited to host-only preparation. Progress to relevant Mac-side tests and native bring-up when their entry, logging and recovery requirements are concretely verified; compilation, emulation and synthetic tests alone do not establish those requirements.

The user still wants to avoid unnecessary risk and may be able to borrow another modern Mac for recovery. External T7 storage does not isolate firmware or boot policy. Authorization for necessary Mac testing is not blanket approval to erase internal storage, bypass installer model checks or change startup security without a concrete reviewed procedure and the required scope. Do not ask again for permission for ordinary Mac-side tests already covered by this clarification.
