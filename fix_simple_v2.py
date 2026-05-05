#!/usr/bin/env python3
"""
Fix missing descriptions - simple version.
Reads preset files and extracts Preset_Notes.
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

# Count presets
presets = [p for p in programs if p.get('entry_type') == 'preset']
print('Total presets:', len(presets))

empty_desc = [p for p in presets if not p.get('description', '').strip()]
print('Presets with empty descriptions:', len(empty_desc))

# Fix presets with empty descriptions
fixed = 0
for prog in programs:
    if prog.get('entry_type') == 'preset' and not prog.get('description', '').strip():
        preset_file = prog.get('preset_file', '')
        if not preset_file:
            continue
        
        # Find the preset file
        file_path = Path(preset_file)
        if not file_path.exists():
            # Try with wine prefix
            file_path = Path('downloads/wine_spooky') / preset_file.replace('downloads/wine_spooky', '')
        
        if not file_path.exists():
            continue
        
        # Read the file and extract Preset_Notes
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as pf:
                content = pf.read()
            
            # Find Preset_Notes= line
            lines = content.split('\n')
            in_notes = False
            notes_lines = []
            
            for line in lines:
                if line.startswith('"Preset_Notes='):
                    in_notes = True
                    # Extract first part (after = and opening quote)
                    first_part = line.split('=', 1)[1] if '=' in line else ''
                    if first_part.startswith('"'):
                        first_part = first_part[1:]  # Remove opening quote
                    notes_lines.append(first_part)
                elif in_notes:
                    if line.startswith('"'):
                        # Continuation line
                        value_part = line[1:] if line.startswith('"') else line
                        notes_lines.append(value_part)
                    else:
                        # End of multi-line
                        in_notes = False
            
            if notes_lines:
                description = '\n'.join(notes_lines)
                # Remove trailing quote if present
                description = description.rstrip('"').rstrip()
                if description:
                    prog['description'] = description
                    fixed += 1
                    if fixed <= 5:
                        print('Fixed:', prog['name'][:60], '-', description[:60])
        
        except Exception as e:
            pass

print('\nFixed', fixed, 'presets with missing descriptions')

# Save updated data
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Done! JSON data updated.')
