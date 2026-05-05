#!/usr/bin/env python3
"""
Fix missing descriptions by reading preset files.
Handles multi-line Preset_Notes properly.
Uses a simple class to maintain state instead of nonlocal.
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

# Build map of preset files
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

class PresetParser:
    """Parse preset file and extract Preset_Notes."""
    
    def extract_notes(self, filepath):
        """Extract Preset_Notes from a preset file (handles multi-line)."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        
            if '[Preset]' not in content:
                return None
    
            # Find all [Preset] sections
            sections = re.split(r'\[/Preset\]', content)
            for section in sections:
                if '[Preset]' not in section:
                    continue
            
                section_body = section.split('[Preset]')[1]
    
                # Parse key=value pairs, handling multi-line
                data = {}
                current_key = None
                current_value_lines = []
    
                def save_current():
                    if current_key is not None:
                        data[current_key] = '\n'.join(current_value_lines)
                        current_key = None
                        current_value_lines = []
    
                lines = section_body.splitlines()
                for line in lines:
                    line = line.rstrip('\n')
                    if not line:
                        continue
    
                    # Check if this is a new "Key=value" line
                    m = re.match(r'^"([^"]+)="([^"]*)"$', line)
                    if m:
                        save_current()
                        key = m.group(1)
                        value = m.group(2)
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

parser = PresetParser()

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
            notes = parser.extract_notes(actual_file)
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
