#!/usr/bin/env python3
"""
Generate sample Spooky2 preset data for development/testing.

Creates a minimal JSON dataset with diverse frequency programs
to test the search and display features.
"""

import json
import uuid
from pathlib import Path

SAMPLE_PROGRAMS = [
    {
        "name": "Detoxification",
        "description": "Full body detoxification using Spooky2 frequencies.",
        "code": "10000,10000,10000,10000,10000,10000,10000,10000,10000,10000",
        "collection": "Factory/Detox/Contact",
        "mode": "Contact",
        "category": "Detox",
        "preset_file": "detox.txt"
    },
    {
        "name": "HIV - Initial",
        "description": "For HIV initial treatment - contact mode.",
        "code": "727=600,727=600,10000 W1 A05 O50",
        "collection": "Factory/HIV/Contact",
        "mode": "Contact",
        "category": "HIV",
        "preset_file": "hiv_initial.txt"
    },
    {
        "name": "Cancer - Breast",
        "description": "Breast cancer frequencies using recommended protocol.",
        "code": "20-20000=1800,20-20000=1800,20-20000=1800",
        "collection": "Factory/Cancer/Contact",
        "mode": "Contact",
        "category": "Cancer",
        "preset_file": "cancer_breast.txt"
    },
    {
        "name": "Cold & Flu",
        "description": "Relieve symptoms of cold and influenza.",
        "code": "1500,1500,1500,10000,10000,10000",
        "collection": "Factory/Illness/Contact",
        "mode": "Contact",
        "category": "Illness",
        "preset_file": "cold_flu.txt"
    },
    {
        "name": "Healing - General",
        "description": "General healing and recovery frequencies.",
        "code": "727=600 W0 A05 O00 G1, 880=600 W0 A05 O00 G1, 2.5=5 W0 A05 O00 G1",
        "collection": "Factory/Healing/Remote",
        "mode": "Remote",
        "category": "Healing",
        "preset_file": "general_healing.txt"
    },
    {
        "name": "Rife Frequency - TB",
        "description": "Rife tuberculosis frequencies (TB).",
        "code": "800,800,800,712,712,712,712,712,712,712,712,712,712,712,712",
        "collection": "Factory/RIFE/TB/Contact",
        "mode": "Contact",
        "category": "RIFE",
        "preset_file": "rife_tb.txt"
    },
    {
        "name": "Parasites - General",
        "description": "Anti-parasitic frequencies for common organisms.",
        "code": "20000-40000=1200 W1 A09 O50 G1",
        "collection": "Factory/Parasites/Contact",
        "mode": "Contact",
        "category": "Parasites",
        "preset_file": "parasites.txt"
    },
    {
        "name": "Stress Relief",
        "description": "Frequency program for stress and anxiety relief.",
        "code": "10,10,10,10,10,10,10,10,10,10, 10000,10000,10000",
        "collection": "Factory/Emotional/Remote",
        "mode": "Remote",
        "category": "Emotional",
        "preset_file": "stress.txt"
    },
    {
        "name": "Pain Relief",
        "description": "Alleviate pain using specific frequencies.",
        "code": "340,340,340,434,434,434,434,727=600,727=600",
        "collection": "Factory/Pain/Contact",
        "mode": "Contact",
        "category": "Pain",
        "preset_file": "pain.txt"
    },
    {
        "name": "DNA Repair",
        "description": "DNA and cellular repair frequencies.",
        "code": "304,304,304,18000,18000,18000,2.5=3,2.5=3",
        "collection": "Factory/DNA/Remote",
        "mode": "Remote",
        "category": "DNA",
        "preset_file": "dna_repair.txt"
    },
    {
        "name": "Blood Pressure",
        "description": "Normalize blood pressure levels.",
        "code": "10000=120, 2.5=120, 727=120",
        "collection": "Factory/Circulation/Contact",
        "mode": "Contact",
        "category": "Circulation",
        "preset_file": "blood_pressure.txt"
    },
    {
        "name": "Stomach Ache",
        "description": "Relieve stomach discomfort and pain.",
        "code": "20,20,20,787=600,787=600",
        "collection": "Factory/Digestive/Contact",
        "mode": "Contact",
        "category": "Digestive",
        "preset_file": "stomach_ache.txt"
    }
]


def main():
    output_dir = Path(__file__).parent.parent / 'data' / 'presets'
    output_dir.mkdir(parents=True, exist_ok=True)

    programs = []
    for raw in SAMPLE_PROGRAMS:
        program = {
            "id": str(uuid.uuid4()),
            "name": raw["name"],
            "description": raw["description"],
            "code": raw["code"],
            "preset_file": raw["preset_file"],
            "collection": raw["collection"],
            "mode": raw["mode"],
            "category": raw.get("category"),
            "default_dwell": 600,
        }
        # Compute frequencies via the JS parser logic (mirrored)
        # For simplicity, use basic parsing in Python for sample
        program["frequencies"] = parse_sample_code(raw["code"])
        programs.append(program)

    # Write combined JSON
    out = {
        "meta": {
            "generated_at": "2026-05-03T00:00:00",
            "source": "sample-data",
            "total_programs": len(programs)
        },
        "programs": programs
    }

    out_path = output_dir / 'presets_all.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # Also create by_collection
    by_coll = {}
    for p in programs:
        coll = p["collection"]
        by_coll.setdefault(coll, []).append(p)

    coll_dir = output_dir / 'by_collection'
    coll_dir.mkdir(exist_ok=True)
    for coll, items in by_coll.items():
        safe = coll.replace('/', '_')
        with open(coll_dir / f'{safe}.json', 'w') as f:
            json.dump({"programs": items}, f, indent=2)

    print(f"Generated {len(programs)} sample programs in {output_dir}")


def parse_sample_code(code):
    """Simple frequency parser for sample data."""
    tokens = []
    for raw_part in code.split(','):
        part = raw_part.strip()
        if not part:
            continue

        # Split off any trailing modifiers (W, A, O, G, etc.)
        # Take only the leading number/sweep part
        base = part
        for mod_prefix in [' W', ' A', ' O', ' G', ' F', ' C', ' M', ' B']:
            if mod_prefix in base:
                base = base.split(mod_prefix)[0]

        base = base.strip()

        if '-' in base and '=' in base:
            # Sweep with dwell: "100-200=1800"
            range_part, dwell_part = base.split('=')
            start, end = range_part.split('-')
            tokens.append({
                "type": "sweep",
                "freq": parse_number(start),
                "endFreq": parse_number(end),
                "dwell": int(dwell_part)
            })
        elif '-' in base:
            start, end = base.split('-')
            tokens.append({
                "type": "sweep",
                "freq": parse_number(start),
                "endFreq": parse_number(end)
            })
        elif '=' in base:
            freq, dwell = base.split('=')
            tokens.append({
                "type": "frequency",
                "freq": parse_number(freq),
                "dwell": int(dwell)
            })
        else:
            try:
                tokens.append({"type": "frequency", "freq": parse_number(base)})
            except:
                pass
    return tokens


def parse_number(s):
    """Parse number as int if possible, else float."""
    try:
        return int(s)
    except ValueError:
        return float(s)


if __name__ == '__main__':
    main()
