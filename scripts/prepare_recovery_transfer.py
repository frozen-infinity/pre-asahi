#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare private transfer files from an already verified decoded recovery image."""
import argparse
import json
import os
from pathlib import Path
import shutil
import inspect_recovery_portable as inspector

ROOT = Path(__file__).resolve().parents[1]


def prepare(image):
    inspector.verify(image)
    folder = ROOT / 'work/recovery-check-for-second-mac'
    folder.mkdir(parents=True, exist_ok=False)
    target = folder / 'BaseSystem.dmg'
    # Local hard link saves 1.56 GB; Finder copying this folder to another Mac
    # materializes ordinary image bytes. The checker never modifies the image.
    try:
        os.link(image, target)
    except OSError:
        shutil.copyfile(image, target)
    inspector.verify(target)
    shutil.copy2(ROOT / 'scripts/inspect_recovery_portable.py', folder / 'inspect_recovery.py')
    shutil.copy2(ROOT / 'LICENSE', folder / 'LICENSE')
    shutil.copy2(ROOT / 'docs/second-mac-check.md', folder / 'READ-ME-FIRST.md')
    (folder / 'transfer-manifest.json').write_text(json.dumps({
        'image_bytes': inspector.IMAGE_BYTES, 'image_sha256': inspector.IMAGE_SHA,
        'image_is_not_a_bootable_installer': True, 'content_inspection_performed': False,
        'native_boot_proven': False}, indent=2) + '\n')
    print(folder)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.image.resolve())
