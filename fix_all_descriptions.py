#!/usr/bin/env python3
"""
Fix missing descriptions by reading preset files and extracting Preset_Notes.
"""
import json
import re
from pathlib import Path

json_path = Path('spooky2-search/public/data/presets_all.json')
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

programs = data.get('programs', [])
print(f'Total programs: {len(programs)}')

# Build a map of preset_name -> file path
preset_dir = Path('downloads/wine_spooky/drive_c/Spooky2/Preset Collections')
preset_files = {}
for txt_file in preset_dir.rglob('*.txt'):
    # Store the first file found for each preset name
    name = txt_file.stem
    if name not in preset_files:
        preset_files[name] = txt_file

print(f'Found {len(preset_files)} preset files')

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
                
                # Check if this is a new "Key=value" line
                m = re.match(r'^"([^"]+)="([^"]*)"$', line)
                if m:
                    save_current()
                    key, value = m.group(1), m.group(2)
                    current_key = key
                    current_value_lines = [value]
                elif line.startswith('"'):
                    # Continuation of multi-line value
                    if current_key is not None:
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

fixed = 0
for prog in programs:
    if prog.get('entry_type') == 'preset' and not prog.get('description', '').strip():
        preset_name = prog['name']
        # Try to find the preset file
        file_path = preset_files.get(preset_name)
        if not file_path:
            # Try searching with partial name
            for name, path in preset_files.items():
                if preset_name in name or name in preset_name:
                    file_path = path
                    break
        
        if file_path:
            notes = extract_notes(file_path)
            if notes:
                prog['description'] = notes
                fixed += 1
                if fixed <= 5:
                    print(f'Fixed: {preset_name}: {notes[:80]}...')

print(f'\nFixed {fixed} presets with missing descriptions')

# Save the updated data
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Done!')
