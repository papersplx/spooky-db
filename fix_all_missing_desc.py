#!/usr/bin/env python3
"""Fix missing descriptions for presets by reading Preset_Notes from preset files."""
import json
from pathlib import Path
import re

json_path = Path('data/presets/presets_all.json')
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

programs = data.get('programs', [])
print(f'Total programs: {len(programs)}')

presets = [p for p in programs if p.get('entry_type') == 'preset']
print(f'Total presets: {len(presets)}')

empty_presets = [p for p in presets if not p.get('description', '').strip()]
print(f'Presets with empty descriptions: {len(empty_presets)}')

fixed = 0
not_found = 0
no_notes = 0

for prog in empty_presets:
    preset_file = prog.get('preset_file', '')
    if not preset_file:
        continue
    
    # Fix path: add leading / if missing
    if not preset_file.startswith('/'):
        full_path = Path('/' + preset_file)
    else:
        full_path = Path(preset_file)
    
    if not full_path.exists():
        not_found += 1
        if not_found <= 3:
            print(f'File not found: {full_path}')
        continue
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as pf:
            content = pf.read()
        
        # Split by [Preset] sections
        sections = re.split(r'\[/?Preset\]', content)
        
        preset_name = prog['name']
        
        # Find the section that matches this preset's name
        for section in sections:
            if 'PresetName=' not in section:
                continue
            
            # Extract PresetName from this section
            name_match = re.search(r'"PresetName=([^"]*)"', section)
            if not name_match:
                continue
            
            section_name = name_match.group(1)
            
            # Check if this section matches our preset
            # The preset name in JSON might not exactly match the file
            # Try to match by checking if the base name is in the section name
            if section_name in preset_name or preset_name in section_name:
                # Extract Preset_Notes from this section
                notes_match = re.search(r'"Preset_Notes=([^"]*(?:\n[^"\n][^\n]*)*)', section)
                if notes_match:
                    notes = notes_match.group(1).strip()
                    # Clean up
                    notes = re.sub(r'"\s*\n\s*"', '', notes)
                    if notes and notes != '\"':
                        prog['description'] = notes
                        fixed += 1
                        if fixed <= 5:
                            print(f'Fixed ({fixed}): {preset_name[:50]} - {notes[:50]}...')
                        break
        else:
            no_notes += 1
    except Exception as e:
        pass

print(f'\nFixed: {fixed}')
print(f'Not found: {not_found}')
print(f'No Preset_Notes: {no_notes}')

# Save
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f'\nSaved to {json_path}')

# Copy to public
import shutil
public_path = Path('spooky2-search/public/data/presets_all.json')
shutil.copy2(json_path, public_path)
print(f'Copied to {public_path}')
