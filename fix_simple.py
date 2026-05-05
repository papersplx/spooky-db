#!/usr/bin/env python3
"""
Fix missing descriptions by reading preset files directly.
Simple version - handles multi-line Preset_Notes.
"""
import json
import re
from pathlib import Path

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

# Find preset files
wine_base = Path('downloads/wine_spooky/drive_c/Spooky2/Preset Collections')
preset_map = {}

for txt_file in wine_base.rglob('*.txt'):
    # Map by relative path from project root
    rel_path = str(txt_file.relative_to(Path('.')))
    preset_map[rel_path] = txt_file
    # Also map by path from wine prefix
    rel_to_wine = str(txt_file.relative_to(wine_base.parent))
    preset_map[rel_to_wine] = txt_file
    # Also map by filename
    preset_map[txt_file.name] = txt_file

print('Found', len(preset_map), 'preset file paths')

def extract_notes_simple(filepath):
    """Extract Preset_Notes from a preset file (simple approach)."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Find "Preset_Notes=" or [Preset] format
        if 'Preset_Notes=' in content:
            # Find the start of Preset_Notes value
            pos = content.find('Preset_Notes=')
            if pos == -1:
                return None
            
            # Skip past "Preset_Notes="
            pos = content.find('"', pos)
            if pos == -1:
                return None
            
            # Start after the opening quote
            start = pos + 1
            
            # Collect lines until we find a line that doesn't start with "
            lines = []
            remaining = content[start:]
            for line in remaining.split('\n'):
                # Check if this line is part of multi-line value
                # In Spooky2 format, continuation lines start with "
                if line.startswith('"'):
                    # Remove leading quote if present
                    value_part = line[1:] if line.startswith('"') else line
                    lines.append(value_part)
                else:
                    # Non-quote line means end of multi-line
                    break
            
            result = '\n'.join(lines)
            # Remove trailing quote if present
            result = result.rstrip('"').rstrip()
            return result if result else None
        
        return None
    
    except Exception as e:
        return None

# Fix presets with empty descriptions
fixed = 0
for prog in programs:
    if prog.get('entry_type') == 'preset' and not prog.get('description', '').strip():
        preset_file = prog.get('preset_file', '')
        if not preset_file:
            continue
    
        # Try to find the preset file
        actual_file = preset_map.get(preset_file)
        if not actual_file:
            # Try with just the filename
            filename = preset_file.split('/')[-1]
            actual_file = preset_map.get(filename)
    
        if actual_file:
            notes = extract_notes_simple(actual_file)
            if notes:
                prog['description'] = notes
                fixed += 1
                if fixed <= 5:
                    name = prog['name']
                    print('Fixed:', name[:60], '-', notes[:60])

print('\nFixed', fixed, 'presets with missing descriptions')

# Save updated data
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Done! JSON data updated.')
