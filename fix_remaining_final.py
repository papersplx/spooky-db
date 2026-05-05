#!/usr/bin/env python3
"""
Fix remaining presets by extracting Preset_Notes directly.
Correct approach: find Preset_Notes= in file, collect multi-line value.
"""
import json
from pathlib import Path
import re

# Load JSON data
json_path = Path('spooky2-search/public/data/presets_all.json')
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

programs = data.get('programs', [])
print('Total programs:', len(programs))

# Get presets without descriptions
presets = [p for p in programs if p.get('entry_type') == 'preset']
no_desc = [p for p in presets if not p.get('description', '').strip()]

print('Presets without descriptions:', len(no_desc))

# Fix presets with empty descriptions
fixed = 0
for prog in no_desc:
    preset_file = prog.get('preset_file', '')
    if not preset_file:
        continue
    
    # Construct full path (preset_file is relative to project root)
    file_path = Path(preset_file)
    if not file_path.exists():
        continue
    
    # Read file and extract Preset_Notes
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as pf:
            content = pf.read()
        
        # Find Preset_Notes= position
        pos = content.find('Preset_Notes=')
        if pos == -1:
            continue
        
        # Skip past Preset_Notes="
        # Find the opening quote
        quote_pos = content.find('"', pos)
        if quote_pos == -1:
            continue
        
        # Start after the opening quote
        start = quote_pos + 1
        
        # Collect lines until we find a line that doesn't start with "
        remaining = content[start:]
        lines = remaining.split('\n')
        notes_lines = []
        
        for line in lines:
            # Check if this line is part of multi-line value
            # In Spooky2 format, continuation lines start with "
            if line.startswith('"'):
                # Remove leading quote if present
                value_part = line[1:] if line.startswith('"') else line
                notes_lines.append(value_part)
            else:
                # Non-quote line means end of multi-line
                break
        
        if notes_lines:
            description = '\n'.join(notes_lines)
            # Remove trailing quote if present
            description = description.rstrip('"').rstrip()
            if description:
                prog['description'] = description
                fixed += 1
                if fixed <= 5:
                    name = prog['name']
                    print('Fixed:', name[:60], '-', description[:60])
    
    except Exception as e:
        pass

print('\nFixed', fixed, 'presets with missing descriptions')

# Save updated data
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Done! JSON data updated.')
