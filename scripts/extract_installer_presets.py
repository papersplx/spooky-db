#!/usr/bin/env python3
"""
Extract presets from Spooky2 installer by decompressing zlib blocks.
"""
import zlib
import re
import json
import uuid
import os
import sys
from datetime import datetime
from pathlib import Path


def find_zlib_blocks(data, min_size=1000):
    """Find and decompress all zlib blocks in data."""
    blocks = []
    i = 0
    while i < len(data) - 2:
        if data[i] == 0x78 and data[i+1] in (0x01, 0x9C, 0xDA):
            try:
                dec = zlib.decompressobj()
                result = dec.decompress(data[i:i+2000000])
                if len(result) > min_size:
                    blocks.append((i, result))
                    i += 1
            except:
                pass
        i += 1
    return blocks


def parse_preset_section(text):
    """Parse a [Preset] ... [/Preset] section."""
    data = {}
    prev_key = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Well-formed "Key=Value"
        m = re.match(r'^"(\w+)=([^"]*)"$', line)
        if m:
            key, value = m.group(1), m.group(2)
        elif line.startswith('"') and '=' in line:
            rest = line[1:]
            if '=' in rest:
                key, value = rest.split('=', 1)
                if value.endswith('"'):
                    value = value[:-1]
            else:
                key = value = None
            if key:
                prev_key = key
        else:
            first_eq = line.find('=')
            if '=' in line and prev_key is not None:
                candidate = line[:first_eq].strip()
                if not re.match(r'^[a-zA-Z_]\w*$', candidate):
                    key, value = prev_key, line
                else:
                    continue
            else:
                continue

        if key in data:
            data[key] = data[key] + ',' + value
        else:
            data[key] = value

    for k, v in data.items():
        if v.startswith(','):
            data[k] = v[1:]

    return data


def extract_presets_from_block(block_data):
    """Extract all presets from a decompressed block."""
    presets = []

    # Split into preset sections
    sections = re.split(r'\[/Preset\]', block_data)
    for section in sections:
        if '[Preset]' not in section:
            continue
        body = section.split('[Preset]', 1)[1]
        data = parse_preset_section(body)

        if 'PresetName' not in data:
            continue

        name = data.get('PresetName', '')
        description = data.get('Preset_Notes', data.get('CustomName', ''))
        freqs_code = data.get('Loaded_Frequencies', '')
        loaded_programs = data.get('Loaded_Programs', '')

        if not name:
            continue

        presets.append({
            'name': name,
            'description': description,
            'frequencies_code': freqs_code,
            'loaded_programs': loaded_programs,
            'entry_type': 'program' if freqs_code.strip() else 'preset',
        })

    return presets


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <installer.exe> [output.json]")
        sys.exit(1)

    installer_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('presets_extracted.json')

    print(f"Reading {installer_path}...")
    with open(installer_path, 'rb') as f:
        data = f.read()
    print(f"File size: {len(data):,} bytes")

    print("Finding zlib blocks...")
    blocks = find_zlib_blocks(data, min_size=5000)
    print(f"Found {len(blocks)} blocks")

    all_presets = []
    seen_names = set()
    blocks_with_presets = 0

    for offset, block in blocks:
        # Quick check if block contains preset data
        if b'[Preset]' not in block and b'PresetName=' not in block:
            continue

        presets = extract_presets_from_block(block.decode('utf-8', errors='replace'))
        if presets:
            blocks_with_presets += 1
            for p in presets:
                # Deduplicate by name
                key = p['name']
                if key not in seen_names:
                    seen_names.add(key)
                    p['id'] = str(uuid.uuid4())
                    all_presets.append(p)

    print(f"Blocks with presets: {blocks_with_presets}")
    print(f"Total unique presets: {len(all_presets)}")

    # Write output
    output = {
        'meta': {
            'extracted_at': datetime.utcnow().isoformat(),
            'source': str(installer_path),
            'total_presets': len(all_presets),
        },
        'presets': all_presets,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Output written to {output_path}")


if __name__ == '__main__':
    main()
