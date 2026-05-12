#!/usr/bin/env python3
"""
Migrate presets_all.json field names: rename _source → source, _tag → tag
for consistency with database column names.
"""
import json
import sys
from pathlib import Path

def migrate(input_path: Path, output_path: Path = None):
    if output_path is None:
        output_path = input_path
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    programs = data.get('programs', [])
    renamed = 0
    for p in programs:
        if '_source' in p:
            p['source'] = p.pop('_source')
            renamed += 1
        if '_tag' in p:
            p['tag'] = p.pop('_tag')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Migrated {renamed} programs: _source/_tag → source/tag")
    print(f"Written: {output_path}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 migrate_field_names.py <presets_all.json> [output.json]")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    migrate(input_path, output_path)
