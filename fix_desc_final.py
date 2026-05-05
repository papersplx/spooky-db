#!/usr/bin/env python3
"""
Fix missing preset descriptions by reading preset files referenced in preset_file field.
Handles multi-line Preset_Notes properly.
"""
import json
from pathlib import Path
import re

# Load the JSON data
json_path = Path('spooky2-search/public/data/presets_all.json')
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

programs = data.get('programs', [])
print(f'Total programs: {len(programs)}')

# Count presets
presets = [p for p in programs if p.get('entry_type') == 'preset']
print(f'Total presets: {len(presets)}')

# Fix presets with empty descriptions
fixed = 0
for prog in presets:
    if prog.get('description', '').strip():
        continue
    
    preset_file = prog.get('preset_file', '')
    if not preset_file:
        continue
    
    # Construct full path (preset_file is relative to project root)
    full_path = Path(preset_file)
    if not full_path.exists():
        # Try with wine prefix
        full_path = Path('downloads/wine_spooky') / preset_file.replace('downloads/wine_spooky', 'downloads/wine_spooky/drive_c')
    
    if not full_path.exists():
        continue
    
    # Extract Preset_Notes from the preset file
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as pf:
            content = pf.read()
        
        if '[Preset]' not in content:
            continue
            
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
                        # Remove leading quote if present
                        value_part = line[1:] if line.startswith('"') else line
                        current_value_lines.append(value_part)
                else:
                    # Non-quoted line - might be end of multi-line
                    save_current()
            
            save_current()  # Don't forget last value
            
            if 'PresetName' in data:
                notes = data.get('Preset_Notes', '')
                if notes:
                    prog['description'] = notes
                    fixed += 1
                    if fixed <= 5:
                        print(f'Fixed: {prog["name"]}: {notes[:80]}...')
                    break
    
    except Exception as e:
        pass

print(f'\nFixed {fixed} presets with missing descriptions')

# Save the updated data
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Done! JSON data updated.')
