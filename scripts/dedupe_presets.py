#!/usr/bin/env python3
"""
Deduplicate Spooky2 preset programs by removing entries with identical
name and code, keeping the "best" version of each.

Dedup strategy:
- Group programs by (name, code) key
- For each group with >1 entry, keep the "best" version:
  1. Prefer the entry with the longer description (more info)
  2. If descriptions are equal length, prefer shorter preset_file path
     (direct file over chain-derived entry)
  3. If still tied, keep the first encountered
- Programs with unique (name, code) pairs pass through unchanged

Usage:
    python3 scripts/dedupe_presets.py data/presets/presets_all.json
    python3 scripts/dedupe_presets.py data/presets/presets_all.json -o data/presets/presets_deduped.json
"""
import json
import sys
from pathlib import Path
from collections import defaultdict


def load_data(filepath: str) -> dict:
    """Load and return JSON data from the given path."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def dedupe_programs(programs: list[dict]) -> tuple[list[dict], dict]:
    """
    Remove duplicate programs where both name and code match.

    Returns:
        - Deduplicated list of programs
        - Stats dict with counts of processed/removed/kept entries
    """
    # Group by (name, code) key
    groups = defaultdict(list)
    for prog in programs:
        key = (prog.get('name', ''), prog.get('code', ''))
        groups[key].append(prog)

    kept = 0
    removed = 0
    exact_dupes = 0       # name + code + description all identical
    desc_diff_dupes = 0   # name + code match, description differs
    unique_entries = 0    # no duplicates at all

    result = []

    for key, group in groups.items():
        if len(group) == 1:
            # Unique entry, keep as-is
            result.append(group[0])
            unique_entries += 1
            kept += 1
            continue

        # Sort group to ensure deterministic selection.
        # Primary: prefer longer description (more info).
        # Secondary: prefer shorter preset_file path (more direct source).
        # Tertiary: stable order (first encountered wins).
        group.sort(key=lambda p: (
            -len(p.get('description', '')),
            len(p.get('preset_file', '')),
        ))

        winner = group[0]
        losers = group[1:]

        result.append(winner)
        kept += 1
        removed += len(losers)

        # Categorize for stats
        descs = set(p.get('description', '') for p in group)
        if len(descs) == 1:
            exact_dupes += 1
        else:
            desc_diff_dupes += 1

    stats = {
        'total_input': len(programs),
        'total_output': len(result),
        'removed': removed,
        'kept': kept,
        'unique_entries': unique_entries,
        'exact_duplicate_groups': exact_dupes,
        'description_diff_groups': desc_diff_dupes,
    }

    return result, stats


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Deduplicate Spooky2 preset programs by name+code'
    )
    parser.add_argument(
        'input',
        type=str,
        help='Path to input presets_all.json'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Path to output deduplicated JSON (default: overwrite input)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Report duplicates without writing output'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print details of each duplicate group'
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        return 1

    # Load data
    data = load_data(str(input_path))
    programs = data.get('programs', [])
    meta = data.get('meta', {})

    print(f"Loaded {len(programs)} programs from {input_path}")

    # Deduplicate
    deduped, stats = dedupe_programs(programs)

    print(f"\nDeduplication Results:")
    print(f"  Input programs:    {stats['total_input']}")
    print(f"  Output programs:   {stats['total_output']}")
    print(f"  Removed:           {stats['removed']}")
    print(f"  Unique entries:    {stats['unique_entries']}")
    print(f"  Exact dup groups:  {stats['exact_duplicate_groups']}")
    print(f"  Desc-diff groups:  {stats['description_diff_groups']}")

    if args.dry_run:
        print("\nDry run complete. No files written.")
        return 0

    # Write output
    output_data = {
        'meta': {
            **meta,
            'deduplicated_at': meta.get('extracted_at', ''),
            'dedup_removed': stats['removed'],
            'dedup_original_count': stats['total_input'],
        },
        'programs': deduped,
    }

    output_path = Path(args.output) if args.output else input_path
    with open(str(output_path), 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nOutput written to: {output_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())