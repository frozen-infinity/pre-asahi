#!/usr/bin/env python3
"""Locate reviewed native-boot code in pinned local sources. Never contacts hardware."""
import argparse
import hashlib
import json
import subprocess
import sys
import bringup

PINS = {'m1n1': '51b747dced07a58eacf5dabc31ed6f00bcfa20fd',
        'linux': '94fb23346d522edf53722357c426a3e58030beea'}
RULES = [
    ('idle_and_delay_arguments', 'm1n1', 'src/kboot.c', [' idle=nop arm64.nowfxt']),
    ('secondary_ctrr_reservation', 'm1n1', 'src/kboot.c',
     ['fdt_add_mem_rsv(dt, ro_start, ro_end - ro_start)']),
    ('wfe_before_kernel_handoff', 'm1n1', 'src/kboot.c', ['smp_set_wfe_mode(true)']),
    ('locked_reset_vector_handling', 'm1n1', 'src/smp.c',
     ['if (cpu_features->apple_sysregs_unlocked)', 'write64(cpu->impl_reg, (u64)_vectors_start)']),
    ('m4_cpu_features', 'm1n1', 'src/chickens.c',
     ['features_m4 =', 'SLEEP_NONE', 'MIDR_PART_T8132_DONAN_ECORE']),
    ('gxf_initialization_guard', 'm1n1', 'src/main.c', ['if (supports_gxf())']),
    ('kernel_idle_parameter', 'linux', 'arch/arm64/kernel/idle.c',
     ['early_param("idle", setup_idle)', '"nop"']),
    ('j713_uart_dt', 'linux', 'arch/arm64/boot/dts/apple/t8132-jxxx.dtsi',
     ['stdout-path = "serial0"', '&serial0']),
]

def report_sources(lock, sources):
    if any(lock.get(name, {}).get('commit') != sha for name, sha in PINS.items()):
        raise ValueError('Source revisions changed; review before applying these audit rules')
    evidence = []
    for name, repo, path, needles in RULES:
        source = sources[(repo, path)]
        lines = source.splitlines()
        anchors = [{'text': needle, 'lines': [i + 1 for i, line in enumerate(lines) if needle in line]}
                   for needle in needles]
        evidence.append({'name': name, 'repository': repo, 'path': path,
                         'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                         'anchors': anchors, 'all_anchors_found': all(x['lines'] for x in anchors)})
    return {'status': 'STATIC_SOURCE_AUDIT_ONLY', 'native_boot_proven': False,
            'hardware_actions_performed': False, 'source_revisions': PINS,
            'missing_anchor_groups': [x['name'] for x in evidence if not x['all_anchors_found']],
            'evidence': evidence,
            'note': 'Text anchors locate reviewed code; they do not prove runtime behavior, firmware compatibility, safe provisioning or recovery.'}

def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        lock = bringup.read_lock()
        # Git inspection only: never import or execute upstream proxy clients.
        roots = {name: bringup.checked_source(name, lock) for name in PINS}
        sources = {(repo, path): (roots[repo] / path).read_text()
                   for _, repo, path, _ in RULES}
        report = report_sources(lock, sources)
        bringup.save(bringup.REPORTS / 'native-source-audit.json', report)
        print(json.dumps(report, indent=2))
        return 1 if report['missing_anchor_groups'] else 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as e:
        print('STOP: ' + str(e), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
