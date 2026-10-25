# Project working agreement

- Send code and documentation changes through PRs to frozen-infinity/pre-asahi. Do not push changes directly to main or merge PRs without the user's instruction.
- Keep README instructions current and repeat the immediate user steps in the chat when delivering a PR.
- Preserve the user's T7-first test-storage preference. No destructive disk changes, boot policy changes, or installer bypasses are authorized by that preference.
- Build toward native Linux RAM-only proof using existing Asahi infrastructure before Arch userspace or desktop drivers. Never present compile/emulator/hypervisor results as native hardware success.
- Record tested versus untested behavior, exact source revisions and material blockers. Review current upstream model/firmware support before proposing hardware execution.
- Do not commit reports, device identifiers, upstream trees, build artifacts, or user logs. Review generated archives before publication.
- Run `python3 -m unittest discover -s tests -v` for changes to the preparation scripts. Do not claim upstream builds passed unless they actually ran successfully.
- This project is AI-assisted. Respect upstream contribution and AI policies; no automatic upstream submissions.
