#!/usr/bin/env python3
"""
Fix missing descriptions by reading preset files referenced in preset_file field.
"""
import json
import os
from pathlib import Path
import re

# Load the JSON data
json_path = Path('spooky2-search/public/data/presets_all.json')
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

programs = data.get('programs', [])
print(f'Total programs: {len(programs)}')

# Count presets with/without descriptions
presets = [p for p in programs if p.get('entry_type') == 'preset']
print(f'Total presets: {len(presets)}')

# Build a map of preset files in the Wine prefix
wine_prefix = Path('downloads/wine_spooky/drive_c/Spooky2/Preset Collections')
preset_file_map = {}
for txt_file in wine_prefix.rglob('*.txt'):
    # Store relative path from Spooky2 installation
    rel_path = str(txt_file.relative_to(wine_prefix.parent))
    preset_file_map[rel_path] = txt_file
    # Also store just the filename as fallback
    preset_file_map[txt_file.name] = txt_file

print(f'Found {len(preset_file_map)} preset files in Wine prefix')

def extract_notes(filepath):
    """Extract Preset_Notes from a preset file (handles multi-line)."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    
        if '[Preset]' not in content:
            return None
    
        # Find all sections
        sections = re.split(r'\[/Preset\]', content)
        for section in sections:
            if '[Preset]' not in section:
                continue
            section_body = section.split('[Preset]', 1)[1]
    
            # Parse key=value pairs, handling multi-line
            data = {}
            current_key = None
            current_value_lines = []
    
            def save_current():
                nonlocal current_key, current_value_lines
                if current_key is not None:
                    data[current_key] = '\n'.join(current_value_lines)
                    current_key = None
                    current_value_lines = []
    
            for line in section_body.splitlines():
                line = line.rstrip('\n')
                if not line:
                    continue
    
                # Check if this is a new "Key="value" line
                m = re.match(r'^"([^"]+)="([^"]*)"$', line)
                if m:
                    save_current()
                    key, value = m.group(1), m.group(2)
                    current_key = key
                    current_value_lines = [value]
                elif line.startswith('"'):
                    # Continuation of multi-line value
                    if current_key is not None:
                        # Remove leading quote if present
                        value_part = line[1:] if line.startswith('"') else line
                        current_value_lines.append(value_part)
                else:
                    # Non-quoted line - might be end of multi-line
                    save_current()
    
            save_current()  # Don't forget last value
    
            if 'PresetName' in data:
                return data.get('Preset_Notes', '')
    
    except Exception as e:
        return None
    
    return None

# Fix presets with empty descriptions
fixed = 0
for prog in programs:
    if prog.get('entry_type') == 'preset' and not prog.get('description', '').strip():
        preset_file = prog.get('preset_file', '')
        if not preset_file:
            continue
    
        # Try to find the preset file
        actual_file = preset_file_map.get(preset_file)
        if not actual_file:
            # Try with just the filename
            filename = Path(preset_file).name
            actual_file = preset_file_map.get(filename)
    
        if actual_file:
            notes = extract_notes(actual_file)
            if notes:
                prog['description'] = notes
                fixed += 1
                if fixed <= 10:
                    print(f'Fixed: {prog["name"][:60]}...')

print(f'\nFixed {fixed} presets with missing descriptions')

# Save the updated data
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Done! JSON data updated.')
