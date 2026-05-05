#!/usr/bin/env python3
"""
Fix missing descriptions in presets_all.json by re-extracting Preset_Notes from preset files.
"""
import json
import re
from pathlib import Path

def extract_description(filepath):
    """Extract Preset_Notes from a preset file (handles multiline)."""
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
            
            # Parse key=value pairs, handling multiline
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
                    # Continuation of multiline value
                    if current_key is not None:
                        value_part = line[1:] if line.startswith('"') else line
                        current_value_lines.append(value_part)
                else:
                    save_current()
            
            save_current()  # Don't forget last value
            
            if 'PresetName' in data:
                return data.get('Preset_Notes', '')
    
    except Exception as e:
        print(f'Error reading {filepath}: {e}')
        return None
    
    return None

# Load the JSON data
json_path = Path('spooky2-search/public/data/presets_all.json')
with open(json_path, 'r') as f:
    data = json.load(f)

programs = data.get('programs', [])
print(f'Total programs: {len(programs)}')

# Find presets without descriptions
fixed = 0
for prog in programs:
    if prog.get('entry_type') == 'preset' and not prog.get('description', '').strip():
        # Try to find the preset file
        preset_file = prog.get('preset_file', '')
        if not preset_file:
            continue
            
        # Construct full path (assuming it's relative to wine prefix)
        # The preset_file field looks like: "Preset Collections/..."
        # We need to find the actual file
        # For now, let's search in the downloads directory
        
        # Extract preset name from program name to search for file
        preset_name = prog['name']
        
        # Search for the preset file
        search_patterns = [
            f'**/*{preset_name}*.txt',
            f'**/*{preset_name.split(" (")[0]}*.txt',
        ]
        
        found_file = None
        for pattern in search_patterns:
            files = list(Path('downloads/wine_spooky/drive_c/Spooky2').rglob(pattern))
            if files:
                found_file = files[0]
                break
        
        if found_file:
            desc = extract_description(found_file)
            if desc:
                prog['description'] = desc
                fixed += 1
                if fixed <= 5:
                    print(f'Fixed: {preset_name}: {desc[:80]}...')

print(f'\nFixed {fixed} presets')

# Save the updated data
with open(json_path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Done!')
