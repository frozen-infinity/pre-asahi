# Contributing

Use a topic branch and a PR. Include the problem, resulting behavior, validation actually performed, limitations, and copyable user steps. Keep hardware-dependent work in draft while its stated gates are unresolved. Do not merge changes on the user's behalf without an instruction.

The current phase is preparation for native RAM-only boot proof. Changes that touch partitions, startup security, boot provisioning, or persistent storage require a separately reviewed plan. A spare external T7 is not blanket authorization to erase any disk.

Run locally:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/bringup.py --help
```

Use `docs/boot-record.example.json` for hardware evidence; do not upload raw device reports without privacy review. A working build is not evidence of a working boot or driver. Review upstream licensing, contribution instructions and AI policy before considering any upstream submission.
