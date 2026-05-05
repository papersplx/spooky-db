#!/usr/bin/env python3
"""
Fixed extraction script - properly handles multiline Preset_Notes.
"""
import os
import re
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

@dataclass
class FrequencyToken:
    freq: Optional[int] = None
    end_freq: Optional[int] = None
    dwell: Optional[int] = None
    waveform: Optional[int] = None
    amplitude: Optional[float] = None
    offset: Optional[int] = None
    gate: Optional[int] = None
    factor: Optional[int] = None
    constant: Optional[int] = None
    molecular: Optional[int] = None
    base_pairs: Optional[int] = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class Program:
    id: str
    name: str
    description: str
    code: str
    frequencies: List[Dict]
    preset_file: str
    collection: str
    mode: str
    category: Optional[str] = None
    default_dwell: Optional[int] = None
    entry_type: str = 'program'
    loaded_programs: Optional[str] = None

    def to_dict(self):
        return asdict(self)

class PresetParser:
    """Parses Spooky2 .txt preset files (multiple formats)."""
    
    WAVEFORM_NAMES = {
        0: "Sine",
        1: "Square",
        2: "Triangle",
        3: "Reverse Sawtooth",
        4: "Sawtooth",
    }

    def __init__(self):
        self.reset()

    def reset(self):
        self.list2 = None
        self.list4 = None
        self.in_multiline = False
        self.multiline_key = None
        self.multiline_value = []

    def parse_line(self, line: str) -> Optional[Tuple[str, str]]:
        line = line.rstrip('\n')
        
        if self.in_multiline:
            if line.startswith('"'):
                self.multiline_value.append(line)
                if not line.endswith('"'):
                    return None
                value = '\n'.join(self.multiline_value)
                result = (self.multiline_key, value)
                self.multiline_key = None
                self.multiline_value = []
                self.in_multiline = False
                return result
            return None
        
        match = re.match(r'^(\w+)\s*=\s*"([^"]*)"', line)
        if match:
            key = match.group(1)
            value = match.group(2)
            if key in ('List2', 'List4'):
                return (key, value)
            return None
        
        match = re.match(r'^(\w+)\s*=\s*"([^"]*)$', line)
        if match:
            key = match.group(1)
            self.in_multiline = True
            self.multiline_key = key
            self.multiline_value = [match.group(2)]
            if line.endswith('"'):
                value = '\n'.join(self.multiline_value)
                result = (self.multiline_key, value)
                self.multiline_key = None
                self.multiline_value = []
                self.in_multiline = False
                return result
            return None
        
        if line.startswith('"'):
            if self.in_multiline:
                self.multiline_value.append(line)
            return None
        
        return None

    def parse_file(self, filepath: Path, base_collection: str) -> List[Program]:
        programs = []
        self.reset()
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        if 'PresetName=' in content:
            programs.extend(self._parse_preset_section_format(filepath, base_collection, content))
        else:
            lines = content.split('\n')
            for line in lines:
                result = self.parse_line(line)
                if result:
                    key, value = result
                    if key == 'List2':
                        self.list2 = value
                    elif key == 'List4':
                        self.list4 = value
                        
                        current_list2 = None
                        current_list4 = None
                        accumulated_list2 = ""
                        accumulated_list4 = ""
                        
                        if 'List2' in line or 'List4' in line:
                            parts = line.split(',')
                            for part in parts:
                                part = part.strip()
                                if 'List2=' in part:
                                    current_list2 = part.split('=', 1)[1] if '=' in part else None
                                    accumulated_list2 = current_list2 or ""
                                elif 'List4=' in part:
                                    current_list4 = part.split('=', 1)[1] if '=' in part else None
                                    accumulated_list4 = current_list4 or ""
                            
                            if current_list4 is not None:
                                program = self._build_program(
                                    filepath, base_collection,
                                    current_list2 or "", current_list4,
                                    accumulated_list2, accumulated_list4
                                )
                                if program:
                                    programs.append(program)
        
        return programs

    def _parse_preset_section_format(self, filepath: Path, base_collection: str, content: str) -> List[Program]:
        """Parse [Preset] style format - handles multiline values."""
        programs = []
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
                
                m = re.match(r'^"([^"]+)="([^"]*)"$', line)
                if m:
                    save_current()
                    key, value = m.group(1), m.group(2)
                    current_key = key
                    current_value_lines = [value]
                elif line.startswith('"'):
                    if current_key is not None:
                        value_part = line[1:] if line.startswith('"') else line
                        current_value_lines.append(value_part)
                else:
                    save_current()
            
            save_current()
            
            if 'PresetName' not in data:
                continue
            
            name = data.get('PresetName', filepath.stem)
            description = data.get('Preset_Notes', data.get('CustomName', ''))
            freqs_code = data.get('Loaded_Frequencies', '')
            loaded_programs = data.get('Loaded_Programs', '')
            
            program_id = str(uuid.uuid4())
            mode = self._detect_mode(filepath, name, description, data.get('Base_Preset', ''))
            collection = base_collection
            category = self._extract_category(base_collection)
            frequencies = self.parse_frequency_code(freqs_code)
            
            if freqs_code.strip() and frequencies:
                entry_type = 'program'
            elif loaded_programs.strip():
                entry_type = 'preset'
            else:
                entry_type = 'preset'
            
            program = Program(
                id=program_id,
                name=name,
                description=description,
                code=freqs_code,
                frequencies=frequencies,
                preset_file=str(filepath.relative_to(Path(filepath).anchor)),
                collection=collection,
                mode=mode,
                category=category,
                default_dwell=None,
                entry_type=entry_type,
                loaded_programs=loaded_programs if loaded_programs else None
            )
            programs.append(program)
        
        return programs

    def _build_program(self, filepath: Path, base_collection: str,
                     list2: str, list4: str, raw_list2: str, raw_list4: str) -> Optional[Program]:
        name = filepath.stem
        first_line = list2.split('\n')[0].strip()
        if first_line and len(first_line) < 100:
            name = first_line
        
        mode = self._detect_mode(filepath, name, list2)
        collection = base_collection
        frequencies = self.parse_frequency_code(list4)
        
        if not frequencies:
            return None
        
        default_dwell = None
        if frequencies and 'dwell' in frequencies[0]:
            default_dwell = frequencies[0]['dwell']
        
        program_id = str(uuid.uuid4())
        
        return Program(
            id=program_id,
            name=name,
            description=list2,
            code=list4,
            frequencies=frequencies,
            preset_file=str(filepath.relative_to(Path(filepath).anchor)),
            collection=collection,
            mode=mode,
            category=self._extract_category(base_collection),
            default_dwell=default_dwell,
            entry_type='program'
        )

    def _detect_mode(self, filepath: Path, name: str, description: str, base_preset: str = '') -> str:
        path_str = str(filepath).lower()
        name_str = name.lower()
        desc_str = description.lower()
        
        if 'remote' in path_str or '(r)' in name_str or 'remote' in desc_str:
            return 'Remote'
        if 'plasma' in path_str or '(p)' in name_str or 'plasma' in desc_str:
            return 'Plasma'
        if 'contact' in path_str or '(c)' in name_str or 'contact' in desc_str:
            return 'Contact'
        if 'coil' in path_str or '(m)' in name_str or 'coil' in desc_str or 'pemf' in desc_str:
            return 'Coil'
        if 'scalar' in path_str or '(s)' in name_str or 'scalar' in desc_str:
            return 'Scalar'
        if 'laser' in path_str or '(l)' in name_str or 'laser' in desc_str:
            return 'Laser'
        return 'Other'

    def _extract_category(self, collection_path: str) -> Optional[str]:
        parts = collection_path.split('/')
        if len(parts) >= 2:
            return parts[1]
        return None

    def parse_frequency_code(self, code: str) -> List[Dict]:
        """Parse Spooky2 frequency code into structured tokens."""
        tokens = []
        current = {
            'waveform': None,
            'amplitude': None,
            'offset': None,
            'gate': None,
            'factor': None,
            'constant': None,
            'molecular': None,
            'basePairs': None,
        }
        
        if not code:
            return tokens
        
        parts = code.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            if part.startswith('~'):
                tokens.append({
                    'type': 'bacon',
                    'raw': part,
                    **current
                })
                continue
            
            sweep_match = re.match(r'^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?:=(\d+))?$', part)
            if sweep_match:
                tokens.append({
                    'type': 'sweep',
                    'freq': float(sweep_match.group(1)),
                    'endFreq': float(sweep_match.group(2)),
                    'dwell': int(sweep_match.group(3)) if sweep_match.group(3) else None,
                    **current
                })
                continue
            
            dwell_match = re.match(r'^(\d+(?:\.\d+)?)=(\d+)$', part)
            if dwell_match:
                tokens.append({
                    'type': 'frequency',
                    'freq': float(dwell_match.group(1)),
                    'dwell': int(dwell_match.group(2)),
                    **current
                })
                continue
            
            if re.match(r'^\d+(?:\.\d+)?$', part):
                tokens.append({
                    'type': 'frequency',
                    'freq': float(part),
                    **current
                })
                continue
            
            w_match = re.match(r'^W(\d+)$', part, re.I)
            if w_match:
                current['waveform'] = int(w_match.group(1))
                continue
            
            a_match = re.match(r'^A(\d+)$', part)
            if a_match:
                current['amplitude'] = int(a_match.group(1))
                continue
            
            o_match = re.match(r'^[Oo](-?\d+)$', part)
            if o_match:
                current['offset'] = int(o_match.group(1))
                continue
            
            g_match = re.match(r'^G([01])$', part)
            if g_match:
                current['gate'] = int(g_match.group(1))
                continue
            
            f_match = re.match(r'^F(\d+)$', part, re.I)
            if f_match:
                current['factor'] = int(f_match.group(1))
                continue
            
            c_match = re.match(r'^C(\d+)$', part, re.I)
            if c_match:
                current['constant'] = int(c_match.group(1))
                continue
            
            m_match = re.match(r'^M(\d+)$', part, re.I)
            if m_match:
                current['molecular'] = int(m_match.group(1))
                continue
            
            b_match = re.match(r'^B(\d+)$', part, re.I)
            if b_match:
                current['basePairs'] = int(b_match.group(1))
                continue
            
            tokens.append({
                'type': 'raw',
                'raw': part,
                **current
            })
        
        return tokens

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract Spooky2 presets to JSON')
    parser.add_argument('input_dir', help='Path to Preset Collections directory')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    presets_dir = Path(args.input_dir)
    if not presets_dir.exists():
        print(f"Error: {presets_dir} not found")
        return
    
    parser = PresetParser()
    all_programs = []
    total_files = 0
    
    for txt_file in presets_dir.rglob('*.txt'):
        if args.verbose:
            print(f"Processing: {txt_file}")
        
        rel_path = str(txt_file.relative_to(presets_dir))
        collection = '/'.join(rel_path.split('/')[:-1])
        
        programs = parser.parse_file(txt_file, collection)
        all_programs.extend(programs)
        total_files += 1
    
    output = {
        'meta': {
            'extracted_at': datetime.now().isoformat(),
            'source': str(presets_dir),
            'total_programs': len(all_programs)
        },
        'programs': [p.to_dict() for p in all_programs]
    }
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Extracted {len(all_programs)} programs from {total_files} files")
    print(f"Output: {args.output}")

if __name__ == '__main__':
    from datetime import datetime
    main()
