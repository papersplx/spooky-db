#!/usr/bin/env python3
"""
Frequency-based fingerprinting for Spooky2 preset deduplication.

Generates canonical fingerprints from frequency tokens to detect programs
with identical or near-identical frequency content, regardless of name
or code formatting differences.

Approach:
- Parse each program's frequency tokens
- Create a canonical fingerprint: sorted list of (freq, type) pairs
- Group programs by fingerprint
- Programs sharing a fingerprint are "frequency duplicates"

Usage:
    python3 scripts/fingerprint_presets.py data/presets/presets_all.json
    python3 scripts/fingerprint_presets.py data/presets/presets_all.json --output data/presets/fingerprints.json
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def extract_fingerprint(frequencies):
    """
    Extract a canonical fingerprint from a list of frequency tokens.
    
    The fingerprint is based on the multiset of frequency values (ignoring
    waveform, amplitude, offset, and other modifiers which are secondary
    characteristics).
    
    Returns a string like "10000x10,144000x1" indicating frequencies and their
    counts, sorted by frequency value.
    """
    if not frequencies:
        return None
    
    # Collect (freq, type) pairs, normalizing freq to a canonical form
    freq_items = []
    for token in frequencies:
        ftype = token.get('type', 'unknown')
        
        if ftype == 'frequency' and token.get('freq') is not None:
            # Normalize frequency to 2 decimal places
            freq = round(float(token['freq']), 2)
            freq_items.append(('frequency', freq))
        
        elif ftype == 'sweep' and token.get('freq') is not None and token.get('end_freq') is not None:
            # For sweeps, use both start and end frequencies
            start = round(float(token['freq']), 2)
            end = round(float(token['end_freq']), 2)
            freq_items.append(('sweep_start', start))
            freq_items.append(('sweep_end', end))
        
        elif ftype == 'bacon':
            # Bacon-encoded frequencies - use the raw value
            raw = token.get('raw', '')
            freq_items.append(('bacon', raw))
    
    if not freq_items:
        return None
    
    # Sort by (type, value) for canonical ordering
    freq_items.sort(key=lambda x: (x[0], x[1]))
    
    # Build a compact fingerprint string
    # Group consecutive identical items and use counts
    parts = []
    i = 0
    while i < len(freq_items):
        ftype, val = freq_items[i]
        count = 1
        while i + count < len(freq_items) and freq_items[i + count] == (ftype, val):
            count += 1
        if count > 1:
            parts.append(f"{val}x{count}")
        else:
            parts.append(str(val))
        i += count
    
    return "|".join(parts)


def find_duplicate_groups(programs):
    """
    Find groups of programs that share the same frequency fingerprint.
    
    Returns:
        - duplicate_groups: list of groups (each group is a list of program dicts)
        - fingerprint_map: dict mapping fingerprint -> list of programs
    """
    fingerprint_map = defaultdict(list)
    no_fingerprint = []
    
    for prog in programs:
        fingerprint = extract_fingerprint(prog.get('frequencies', []))
        if fingerprint is None:
            no_fingerprint.append(prog)
        else:
            fingerprint_map[fingerprint].append(prog)
    
    # Groups with more than one program are duplicates
    duplicate_groups = [
        progs for progs in fingerprint_map.values()
        if len(progs) > 1
    ]
    
    # Sort groups by size (largest first) for reporting
    duplicate_groups.sort(key=lambda g: -len(g))
    
    return duplicate_groups, dict(fingerprint_map), no_fingerprint


def build_fingerprint_index(programs):
    """
    Build a lookup structure: program_id -> list of related program IDs.
    
    Returns a dict mapping each program ID to the list of other program IDs
    that share the same frequency fingerprint.
    """
    fingerprint_map = defaultdict(list)
    
    for prog in programs:
        fingerprint = extract_fingerprint(prog.get('frequencies', []))
        if fingerprint:
            fingerprint_map[fingerprint].append(prog['id'])
    
    # Build reverse lookup
    related = {}
    for prog in programs:
        pid = prog['id']
        fingerprint = extract_fingerprint(prog.get('frequencies', []))
        if fingerprint and fingerprint in fingerprint_map:
            related_ids = [rid for rid in fingerprint_map[fingerprint] if rid != pid]
            if related_ids:
                related[pid] = related_ids
    
    return related


def analyze_and_report(programs):
    """Analyze programs for frequency-based duplicates and print report."""
    duplicate_groups, fingerprint_map, no_fingerprint = find_duplicate_groups(programs)
    
    total_programs = len(programs)
    unique_fingerprints = len(fingerprint_map)
    programs_with_duplicates = sum(len(g) for g in duplicate_groups)
    unique_programs = total_programs - programs_with_duplicates + len(duplicate_groups)
    
    print(f"Frequency Fingerprint Analysis")
    print(f"=" * 50)
    print(f"Total programs:            {total_programs}")
    print(f"Unique fingerprints:       {unique_fingerprints}")
    print(f"Unique programs (deduped): {unique_programs}")
    print(f"Duplicates removable:      {total_programs - unique_programs}")
    print(f"Programs without freqs:    {len(no_fingerprint)}")
    print(f"Duplicate groups:          {len(duplicate_groups)}")
    print()
    
    # Show top duplicate groups
    if duplicate_groups:
        print("Top 10 Duplicate Groups:")
        print("-" * 50)
        for i, group in enumerate(duplicate_groups[:10]):
            names = [p.get('name', '???') for p in group]
            collections = [p.get('collection', '???') for p in group]
            print(f"\nGroup {i + 1} ({len(group)} programs):")
            for name, coll in zip(names, collections):
                print(f"  - {name} [{coll}]")
    
    return {
        'total_programs': total_programs,
        'unique_fingerprints': unique_fingerprints,
        'programs_with_duplicates': programs_with_duplicates,
        'duplicate_groups_count': len(duplicate_groups),
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fingerprint Spooky2 presets by frequency content'
    )
    parser.add_argument(
        'input',
        type=str,
        help='Path to presets_all.json'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output path for fingerprint index JSON'
    )
    parser.add_argument(
        '--related-output',
        type=str,
        default=None,
        help='Output path for related programs JSON'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Analyze without writing output'
    )
    
    args = parser.parse_args()
    
    # Load data
    input_path = Path(args.input)
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    programs = data.get('programs', [])
    print(f"Loaded {len(programs)} programs from {input_path}")
    print()
    
    # Analyze
    stats = analyze_and_report(programs)
    
    if args.dry_run:
        print("\nDry run complete. No files written.")
        return 0
    
    # Build and save fingerprint index
    if args.output:
        fingerprint_index = {}
        for prog in programs:
            fingerprint = extract_fingerprint(prog.get('frequencies', []))
            if fingerprint:
                fingerprint_index[prog['id']] = {
                    'fingerprint': fingerprint,
                    'name': prog.get('name'),
                }
        
        output_data = {
            'meta': {
                'generated_at': datetime.utcnow().isoformat(),
                'source': str(input_path),
                'total_programs': len(programs),
                'total_fingerprints': len(set(v['fingerprint'] for v in fingerprint_index.values())),
            },
            'fingerprints': fingerprint_index,
        }
        
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\nFingerprint index written to: {output_path}")
    
    # Build and save related programs
    if args.related_output:
        related = build_fingerprint_index(programs)
        
        related_output = {
            'meta': {
                'generated_at': datetime.utcnow().isoformat(),
                'source': str(input_path),
                'total_relations': sum(len(v) for v in related.values()),
            },
            'related': related,
        }
        
        related_path = Path(args.related_output)
        with open(related_path, 'w', encoding='utf-8') as f:
            json.dump(related_output, f, indent=2, ensure_ascii=False)
        print(f"Related programs written to: {related_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())