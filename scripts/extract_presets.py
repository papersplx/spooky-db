#!/usr/bin/env python3
"""
Spooky2 Preset Collection Extractor

Parses Spooky2 .txt preset files and converts them to structured JSON.
Handles multiple formats:

1. Legacy format: Key=value pairs where List2=description, List4=frequency code
   (Values may span multiple quoted lines)

2. Modern [Preset] format: INI-style sections with quoted key=value lines:
   [Preset]
   "PresetName=..."
   "Preset_Notes=..."
   "Loaded_Frequencies=..."
   [/Preset]

Frequency codes may contain:
- Numeric frequencies (100, 11162.11)
- Sweeps (100-200, 100-200=1800)
- Dwell specifications (300=600)
- Modifiers (W0, A05, O50, G1, F2, C3, M4, B5)
- Bacon-encoded tokens (~XXXXX) - stored as-is

Output: JSON array of program objects with parsed frequency tokens.
"""

import os
import re
import json
import uuid
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class FrequencyToken:
    """Parsed frequency token with optional modifiers."""
    freq: Optional[int] = None
    end_freq: Optional[int] = None  # For sweeps
    dwell: Optional[int] = None  # Seconds
    waveform: Optional[int] = None  # 0=Sine, 1=Square, etc.
    amplitude: Optional[float] = None  # Volts
    offset: Optional[int] = None  # Percentage (can be negative)
    gate: Optional[int] = None  # 0=off, 1=on
    factor: Optional[int] = None  # Fx factor
    constant: Optional[int] = None  # Cx constant
    molecular: Optional[int] = None  # Mx molecular weight
    base_pairs: Optional[int] = None  # Bx base pairs

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Program:
    id: str
    name: str
    description: str
    code: str  # Raw frequency code string
    frequencies: List[Dict]
    preset_file: str
    collection: str
    mode: str  # Contact, Remote, Plasma, Coil, Scalar, Laser, Other
    category: Optional[str] = None
    default_dwell: Optional[int] = None
    entry_type: str = 'program'  # 'program' | 'preset' | 'reference'
    loaded_programs: Optional[str] = None  # Raw Loaded_Programs string for presets

    def to_dict(self):
        d = asdict(self)
        return d


class PresetParser:
    """Parses Spooky2 .txt preset files (multiple formats)."""

    # Waveform mapping from s2 Waveforms.h (to be verified)
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
        self.list2 = None  # Current description
        self.list4 = None  # Current frequency code
        self.in_multiline = False
        self.multiline_key = None
        self.multiline_value = []

    def parse_line(self, line: str) -> Optional[Tuple[str, str]]:
        """
        Parse a line from a preset file.
        Returns (key, value) tuple if a List2 or List4 entry is found.
        Multiline values are handled across multiple lines.
        """
        line = line.rstrip('\n')

        # Check for continuation of multiline value
        if self.in_multiline:
            # Continuation lines start with a quote
            if line.startswith('"'):
                # This is still part of the value (the leading quote is part of continuation format)
                self.multiline_value.append(line)
                # Check if this line ends with a quote (not followed by newline quote)
                # Actually the format is tricky: each continuation line starts with a quote
                # The final line will be just a quote?
                # Let's use the s2 approach: they read until a line that doesn't start with quote
                # But looking at the files, continuation lines start with a quote and the value,
                # and the end is a line that starts with a quote and nothing else? Need to check.
                # Simpler: s2 reads line by line, accumulating until a line that doesn't
                # start with a quote OR is just a quote.
                if line == '"':
                    self.in_multiline = False
                    value = '\n'.join(self.multiline_value)
                    result = (self.multiline_key, value)
                    self.multiline_key = None
                    self.multiline_value = []
                    return result
                return None
            else:
                # Unexpected: multiline ended without closing quote line
                self.in_multiline = False
                value = '\n'.join(self.multiline_value)
                result = (self.multiline_key, value)
                self.multiline_key = None
                self.multiline_value = []
                # Fall through to process this line

        # Match key=value pattern. Value is quoted.
        # Format: key="value" or key="value\nvalue\n..."
        match = re.match(r'^(\w+)\s*=\s*"([^"]*)"', line)
        if match:
            key = match.group(1)
            value = match.group(2)
            if key in ('List2', 'List4'):
                return (key, value)
            return None

        # Check for multiline start: key="value
        # Actually they might not have the closing quote on same line.
        match = re.match(r'^(\w+)\s*=\s*"([^"]*)$', line)
        if match:
            self.in_multiline = True
            self.multiline_key = match.group(1)
            self.multiline_value = [match.group(2)]
            return None

        # Continuation line format: starts with a quote, then more text, ends possibly with quote
        # The s2 parser: if line starts with quote, it's a continuation. They append line.
        # They stop when line doesn't start with quote.
        if line.startswith('"'):
            self.in_multiline = True
            self.multiline_key = None  # Should already be set
            self.multiline_value = [line]
            return None

        return None

    def parse_file(self, filepath: Path, base_collection: str) -> List[Program]:
        """Parse a single preset file into Program objects."""
        programs = []
        self.reset()

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # Detect format: presence of "PresetName=" indicates new [Preset] section style
        if 'PresetName=' in content:
            programs.extend(self._parse_preset_section_format(filepath, base_collection, content))
        else:
            # Old-style List2/List4 format
            current_list2 = None
            current_list4 = None
            accumulated_list2 = ""
            accumulated_list4 = ""

            for raw_line in content.splitlines():
                parsed = self.parse_line(raw_line)
                if parsed:
                    key, value = parsed
                    if key == 'List2':
                        if current_list4 is not None:
                            program = self._build_program(
                                filepath, base_collection,
                                current_list2 or "", current_list4,
                                accumulated_list2, accumulated_list4
                            )
                            if program:
                                programs.append(program)
                            current_list2 = None
                            current_list4 = None
                            accumulated_list2 = ""
                            accumulated_list4 = ""
                        current_list2 = value
                        accumulated_list2 = value
                    elif key == 'List4':
                        current_list4 = value
                        accumulated_list4 = value
                else:
                    # Handle multiline continuation
                    if self.in_multiline and self.multiline_key:
                        pass  # Continuation values handled in parse_line

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
        """Parse [Preset] style format."""
        programs = []
        # Split into sections; one file may contain multiple presets
        # Each section: "[Preset]" ... "[/Preset]" (or just end of file)
        sections = re.split(r'\[/Preset\]', content)
        for section in sections:
            if '[Preset]' not in section:
                continue
            # Extract everything after [Preset] marker
            section_body = section.split('[Preset]', 1)[1]
            # Parse quoted key=value lines; tolerate missing closing quote and
            # bare continuation lines (e.g. multi-line Loaded_Frequencies where
            # the value is written on subsequent unquoted lines).
            data = {}
            prev_key = None          # last key opened with an unclosed "key=..."
            for line in section_body.splitlines():
                line = line.strip()
                if not line:
                    continue

                # Well-formed "Key=Value"
                m = re.match(r'^"([^"]+)=([^"]*)"$', line)
                if m:
                    key, value = m.group(1), m.group(2)
                elif line.startswith('"') and '=' in line:
                    # Malformed: opening quote but no closing quote.
                    # Subsequent bare "k=v" lines belong to this key.
                    rest = line[1:]
                    if '=' in rest:
                        key, value = rest.split('=', 1)
                        if value.endswith('"'):
                            value = value[:-1]
                    else:
                        key = value = None
                    if key:
                        prev_key = key
                else:
                    # Bare line (no leading quote). If it looks like a bare
                    # "key=value" token and a previous unclosed key exists, it
                    # is a continuation of that key; otherwise skip.
                    first_eq = line.find('=')
                    if '=' in line and prev_key is not None:
                        candidate = line[:first_eq].strip()
                        # Valid Spooky2 keys are single-word identifiers;
                        # bare frequency tokens contain digits/dashes/dots so
                        # `re.match(r'[a-zA-Z_]\w*', candidate)` must NOT
                        # consume the whole candidate.
                        if not re.match(r'^[a-zA-Z_]\w*$', candidate):
                            key, value = prev_key, line
                        else:
                            continue
                    else:
                        continue

                if key in data:
                    data[key] = data[key] + ',' + value
                else:
                    data[key] = value

            # Strip any leading comma left when a malformed "Key= entry was
            # pre-set with an empty value before its first bare line arrived.
            for k, v in data.items():
                if v.startswith(','):
                    data[k] = v[1:]

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

            # Determine entry type
            if freqs_code.strip() and frequencies:
                entry_type = 'program'
            elif loaded_programs.strip():
                entry_type = 'preset'  # Container that loads other programs
            else:
                entry_type = 'preset'  # Empty/utility preset

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
        """Construct a Program object from parsed List2/List4 (legacy format)."""
        name = filepath.stem
        first_line = list2.split('\n')[0].strip()
        if first_line and len(first_line) < 100:
            name = first_line

        mode = self._detect_mode(filepath, name, list2)
        collection = base_collection
        frequencies = self.parse_frequency_code(list4)

        # Skip if no frequency tokens
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
            entry_type='program'  # Legacy format entries are always programs
        )

    def _extract_category(self, collection_path: str) -> Optional[str]:
        """Extract category from collection path like 'Factory/Detox/Contact'."""
        parts = collection_path.split('/')
        if len(parts) >= 2:
            return parts[1]  # e.g., Detox
        return None

    def _detect_mode(self, filepath: Path, name: str, description: str, base_preset: str = '') -> str:
        """
        Detect program mode from file path, preset name, description, or Base_Preset.
        Returns: Contact, Remote, Plasma, Coil, Scalar, Laser, or Unknown
        """
        # Check path parts first
        for part in filepath.parts:
            part_lower = part.lower()
            if part_lower in ('contact', 'remote', 'plasma', 'coil', 'scalar', 'laser'):
                return part.capitalize()

        # Combine all textual sources
        combined = (name + ' ' + description + ' ' + base_preset).upper()

        # Parentheses patterns
        if '(P)' in combined or '(PLASMA)' in combined:
            return 'Plasma'
        if '(R)' in combined or '(REMOTE)' in combined:
            return 'Remote'
        if '(C)' in combined or '(CONTACT)' in combined:
            return 'Contact'
        # Laser
        if '(L)' in combined or '(CL)' in combined or '(LASER)' in combined or '(COLD LASER)' in combined:
            return 'Laser'
        # Coil / PEMF
        if '(COIL)' in combined or '(M)' in combined or ' PEMF' in combined or '(PEMF)' in combined:
            return 'Coil'
        # Scalar
        if '(S)' in combined or '(SCALAR)' in combined or 'SPOOKY SCALAR' in combined:
            return 'Scalar'

        # Prefix codes: RX=Remote, PX=Plasma, CX=Contact?, SX=Scalar, LX=Laser?, MX=Coil?
        if combined.startswith('RX ') or ' RX ' in combined or '(RX)' in combined:
            return 'Remote'
        if combined.startswith('PX ') or ' PX ' in combined or '(PX)' in combined:
            return 'Plasma'
        if combined.startswith('CX ') or ' CX ' in combined or '(CX)' in combined:
            return 'Contact'
        if combined.startswith('SX ') or ' SX ' in combined or '(SX)' in combined:
            return 'Scalar'
        if combined.startswith('LX ') or ' LX ' in combined or '(LX)' in combined:
            return 'Laser'
        if combined.startswith('MX ') or ' MX ' in combined or '(MX)' in combined:
            return 'Coil'

        # Keyword fallback
        combined_lower = combined.lower()
        if 'plasma' in combined_lower:
            return 'Plasma'
        if 'remote' in combined_lower:
            return 'Remote'
        if 'contact' in combined_lower:
            return 'Contact'
        if 'laser' in combined_lower or 'cold laser' in combined_lower:
            return 'Laser'
        if 'coil' in combined_lower or 'pemf' in combined_lower:
            return 'Coil'
        if 'scalar' in combined_lower:
            return 'Scalar'

        return 'Other'

    def parse_frequency_code(self, code: str) -> List[Dict]:
        """
        Parse Spooky2 frequency code string into structured tokens.
        Unknown tokens (like Bacon codes starting with ~) are preserved as 'raw'.
        """
        tokens = []
        current = {
            'waveform': None,
            'amplitude': None,
            'offset': None,
            'gate': None,
            'factor': None,
            'constant': None,
            'molecular': None,
            'base_pairs': None,
        }

        parts = [p.strip() for p in code.split(',') if p.strip()]

        for part in parts:
            # Bacon-encoded frequency
            if part.startswith('~'):
                tokens.append({
                    'type': 'bacon',
                    'raw': part,
                    **current,
                })
                continue

            # Sweep with dwell: "100-200=1800"
            sweep_match = re.match(r'^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?:=(\d+))?$', part)
            if sweep_match:
                start = float(sweep_match.group(1))
                end = float(sweep_match.group(2))
                dwell = int(sweep_match.group(3)) if sweep_match.group(3) else None
                tokens.append({
                    'type': 'sweep',
                    'freq': start,
                    'end_freq': end,
                    'dwell': dwell,
                    **current,
                })
                continue

            # Dwell: "300=600"
            dwell_match = re.match(r'^(\d+(?:\.\d+)?)=(\d+)$', part)
            if dwell_match:
                freq = float(dwell_match.group(1))
                dwell = int(dwell_match.group(2))
                tokens.append({
                    'type': 'frequency',
                    'freq': freq,
                    'dwell': dwell,
                    **current,
                })
                continue

            # Plain frequency
            if re.match(r'^\d+(?:\.\d+)?$', part):
                tokens.append({
                    'type': 'frequency',
                    'freq': float(part),
                    **current,
                })
                continue

            # Modifier commands
            w_match = re.match(r'^W(\d+)$', part, re.IGNORECASE)
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

            f_match = re.match(r'^F(\d+)$', part, re.IGNORECASE)
            if f_match:
                current['factor'] = int(f_match.group(1))
                continue

            c_match = re.match(r'^C(\d+)$', part, re.IGNORECASE)
            if c_match:
                current['constant'] = int(c_match.group(1))
                continue

            m_match = re.match(r'^M(\d+)$', part, re.IGNORECASE)
            if m_match:
                current['molecular'] = int(m_match.group(1))
                continue

            b_match = re.match(r'^B(\d+)$', part, re.IGNORECASE)
            if b_match:
                current['base_pairs'] = int(b_match.group(1))
                continue

            # Unknown / fallback
            tokens.append({
                'type': 'raw',
                'raw': part,
                **current,
            })

        return tokens


def extract_presets(preset_root: Path, output_dir: Path, include_user: bool = True):
    """
    Walk preset_root, parse all .txt files, and output JSON.

    Args:
        preset_root: Path to Preset Collections/ directory
        output_dir: Directory to write JSON output
        include_user: Whether to include User/ collection
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    parser = PresetParser()
    all_programs = []
    stats = {
        'files_processed': 0,
        'programs_found': 0,
        'errors': 0,
        'collections': {}
    }

    # Walk all .txt files
    for root, dirs, files in os.walk(preset_root):
        root_path = Path(root)
        # Determine collection relative path
        rel_path = root_path.relative_to(preset_root)

        # Skip User/ if not including
        if not include_user and 'User' in root_path.parts:
            continue

        # Count files
        txt_files = [f for f in files if f.lower().endswith('.txt')]
        if not txt_files:
            continue

        collection_name = str(rel_path)
        stats['collections'][collection_name] = 0

        for txt_file in txt_files:
            filepath = root_path / txt_file
            try:
                programs = parser.parse_file(filepath, collection_name)
                for prog in programs:
                    all_programs.append(prog.to_dict())
                    stats['programs_found'] += 1
                stats['files_processed'] += 1
                stats['collections'][collection_name] += len(programs)
            except Exception as e:
                print(f"Error parsing {filepath}: {e}")
                stats['errors'] += 1

    # Write combined index
    combined_path = output_dir / 'presets_all.json'
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'extracted_at': datetime.utcnow().isoformat(),
                'source': str(preset_root),
                'total_programs': len(all_programs)
            },
            'programs': all_programs
        }, f, indent=2, ensure_ascii=False)

    # Also write individual collection files for lazy loading if needed
    by_collection = {}
    for prog in all_programs:
        coll = prog['collection']
        if coll not in by_collection:
            by_collection[coll] = []
        by_collection[coll].append(prog)

    coll_dir = output_dir / 'by_collection'
    coll_dir.mkdir(exist_ok=True)
    for coll, progs in by_collection.items():
        safe_name = coll.replace('/', '_').replace('\\', '_')
        with open(coll_dir / f'{safe_name}.json', 'w', encoding='utf-8') as f:
            json.dump({'programs': progs}, f, indent=2, ensure_ascii=False)

    # Write stats
    stats_path = output_dir / 'extraction_stats.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)

    print(f"Extraction complete:")
    print(f"  Files processed: {stats['files_processed']}")
    print(f"  Programs found: {stats['programs_found']}")
    print(f"  Collections: {len(stats['collections'])}")
    print(f"  Output: {combined_path}")
    print(f"\nTop collections:")
    for coll, count in sorted(stats['collections'].items(), key=lambda x: -x[1])[:10]:
        print(f"  {coll}: {count}")


def main():
    parser = argparse.ArgumentParser(description='Extract Spooky2 preset collections to JSON')
    parser.add_argument('preset_dir', type=str, help='Path to Preset Collections directory')
    parser.add_argument('--output', '-o', type=str, default='./data/presets',
                        help='Output directory for JSON files')
    parser.add_argument('--no-user', action='store_true',
                        help='Exclude User/ collection')

    args = parser.parse_args()

    preset_root = Path(args.preset_dir)
    if not preset_root.exists():
        print(f"Error: {preset_root} does not exist")
        print("You need to download and extract the Spooky2 installer first.")
        print("The Preset Collections folder is inside the installation directory.")
        return 1

    output_dir = Path(args.output)
    extract_presets(preset_root, output_dir, include_user=not args.no_user)

    return 0


if __name__ == '__main__':
    exit(main())
