#!/usr/bin/env python3
"""
Merge presets extracted from new installers into the existing database.
"""
import json
import uuid
import re
from datetime import datetime, timezone
from pathlib import Path


def detect_mode(name, description=''):
    """Detect program mode from name/description."""
    combined = (name + ' ' + description).upper()

    if '(P)' in combined or '(PLASMA)' in combined:
        return 'Plasma'
    if '(R)' in combined or '(REMOTE)' in combined:
        return 'Remote'
    if '(C)' in combined or '(CONTACT)' in combined:
        return 'Contact'
    if '(L)' in combined or '(CL)' in combined or '(LASER)' in combined or '(COLD LASER)' in combined:
        return 'Laser'
    if '(COIL)' in combined or '(M)' in combined or ' PEMF' in combined or '(PEMF)' in combined:
        return 'Coil'
    if '(S)' in combined or '(SCALAR)' in combined or 'SPOOKY SCALAR' in combined:
        return 'Scalar'

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

    combined_lower = (name + ' ' + description).lower()
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


def parse_frequency_code(code):
    """Parse Spooky2 frequency code string into structured tokens."""
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
        if not part:
            continue

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


def infer_collection_name(name, mode):
    """Infer collection path from preset name."""
    # Use mode as subcollection
    mode_dir = mode.capitalize() if mode != 'Other' else 'Contact'

    # Common collection patterns
    name_lower = name.lower()

    if 'peptide' in name_lower or '- jd' in name_lower or '(jd)' in name_lower:
        return f'JW_Peptides/{mode_dir}'
    elif 'dna' in name_lower or name.startswith('DNA '):
        return f'DNA/Viruses/{mode_dir}'
    elif 'morgellons' in name_lower or 'lyme' in name_lower:
        return f'Morgellons and Lyme/Morgellons & Lyme Support'
    elif 'cancer' in name_lower or 'tumor' in name_lower or 'carcinoma' in name_lower:
        return f'Cancer/{mode_dir}'
    elif 'detox' in name_lower or 'heavy metal' in name_lower:
        return f'Detox/{mode_dir}'
    elif 'covid' in name_lower or 'coronavirus' in name_lower or 'sars' in name_lower:
        return f'COVID-19/{mode_dir}'
    elif 'virus' in name_lower or 'bacteria' in name_lower or 'parasite' in name_lower:
        return f'Environmental/{mode_dir}'
    elif 'biofeedback' in name_lower or 'scan' in name_lower:
        return f'Biofeedback/{mode_dir}'
    elif 'heal' in name_lower or ' healing' in name_lower:
        return f'Heal/{mode_dir}'
    elif 'sweep' in name_lower:
        return f'Frequency Sweeps/{mode_dir}'
    elif 'radionics' in name_lower or ' rife' in name_lower or name.startswith('Rife'):
        return f'Radionics/{mode_dir}'
    else:
        return f'Miscellaneous/{mode_dir}'


def main():
    db_path = Path('/var/home/fra/dev/spooky-db/data/presets/presets_all.json')

    # Load existing database
    print(f"Loading existing database from {db_path}...")
    with open(db_path, 'r', encoding='utf-8') as f:
        db = json.load(f)

    existing_names = {p['name'] for p in db['programs']}
    print(f"Existing: {len(db['programs'])} programs, {len(existing_names)} unique names")

    # Load new presets
    new_files = [
        ('/tmp/spooky2_20260826a_presets.json', 'Spooky2_Setup_20260826a'),
        ('/tmp/peptide_20260902_presets.json', 'Peptide_Presets_20260902'),
        ('/tmp/newport_20260903_presets.json', 'Newport_Presets_20260903'),
    ]

    total_added = 0
    source_files = []

    for path, source_name in new_files:
        with open(path, 'r', encoding='utf-8') as f:
            new_data = json.load(f)

        added = 0
        for p in new_data['presets']:
            if p['name'] in existing_names:
                continue
            if not p['frequencies_code'].strip():
                continue

            mode = detect_mode(p['name'], p['description'])
            collection = infer_collection_name(p['name'], mode)
            frequencies = parse_frequency_code(p['frequencies_code'])

            if not frequencies:
                continue

            program = {
                'id': p.get('id') or str(uuid.uuid4()),
                'name': p['name'],
                'description': p['description'],
                'code': p['frequencies_code'],
                'frequencies': frequencies,
                'preset_file': f"{source_name}/{p['name']}.txt",
                'collection': collection,
                'mode': mode,
                'category': collection.split('/')[1] if '/' in collection else collection,
                'default_dwell': None,
                'entry_type': p.get('entry_type', 'program'),
                'loaded_programs': p.get('loaded_programs') or None,
            }

            db['programs'].append(program)
            existing_names.add(p['name'])
            added += 1
            total_added += 1

        print(f"  {source_name}: added {added} new programs")
        if added > 0:
            source_files.append(source_name)

    # Update metadata
    now = datetime.now(timezone.utc).isoformat()
    db['meta']['extracted_at'] = now
    db['meta']['total_programs'] = len(db['programs'])
    db['meta']['last_update'] = now
    db['meta']['last_update_sources'] = source_files
    db['meta']['last_update_added'] = total_added

    print(f"\nTotal new programs added: {total_added}")
    print(f"New total: {len(db['programs'])}")

    # Backup original
    backup_path = db_path.with_suffix('.json.bak')
    print(f"Backing up to {backup_path}")
    db_path.rename(backup_path)

    # Write updated database
    print(f"Writing updated database to {db_path}...")
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

    print("Done!")


if __name__ == '__main__':
    main()
