#!/usr/bin/env python3
"""
Integrate Telegram-downloaded Spooky2 preset files into the extraction pipeline.

This script:
1. Scans data/presets/telegram_raw/ for postprocessed .txt files
2. Reads collection info from the postprocessed directory structure
3. Deduplicates against existing data/presets/presets_all.json
4. Extracts programs from new files using the PresetParser
5. Merges them into the main presets_all.json with proven/unproven tags
6. Saves Telegram group update timestamps for the API

Usage:
    python3 integrate_telegram.py                          # Merge only new files
    python3 integrate_telegram.py --reextract              # Re-extract everything
    python3 integrate_telegram.py --reextract --clean      # Clean re-extract
    python3 integrate_telegram.py --dry-run                # Show what would be done
"""

import os
import sys
import json
import argparse
import hashlib
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from extract_presets import PresetParser, Program


TELEGRAM_RAW_DIR = Path(__file__).parent.parent / "data" / "presets" / "telegram_raw"
DATA_DIR = Path(__file__).parent.parent / "data" / "presets"
PRESETS_ALL = DATA_DIR / "presets_all.json"
BACKUP_DIR = DATA_DIR / "backups"

# Map group slugs to collection tags
GROUP_TAG_MAP = {
    "sp2unoffiles1": "Proven",
    "s2_unof_unproven": "Unproven",
}


def compute_file_hash(filepath: Path) -> str:
    """Compute MD5 hash of a file's content."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_existing_presets() -> Dict:
    """Load the existing presets_all.json."""
    if not PRESETS_ALL.exists():
        return {"meta": {}, "programs": []}
    with open(PRESETS_ALL, "r", encoding="utf-8") as f:
        return json.load(f)


def get_existing_hashes(data: Dict) -> Dict[str, str]:
    """Build a map of program_id -> name for deduplication."""
    return {p["id"]: p["name"] for p in data.get("programs", [])}


def get_existing_names(data: Dict) -> Set[str]:
    """Get set of all existing program names for dedup."""
    return set(p["name"] for p in data.get("programs", []))


def get_file_hashes(data_dir: Path) -> Dict[str, str]:
    """Get hashes of all existing source files."""
    hashes = {}
    for prog_file in data_dir.rglob("*.txt"):
        hashes[compute_file_hash(prog_file)] = str(prog_file)
    return hashes


def get_timestamp_for_group(group_dir: Path) -> str:
    """Get the last-modified timestamp for a group directory."""
    newest_mtime = 0.0
    for f in group_dir.rglob("*"):
        if f.is_file():
            mtime = f.stat().st_mtime
            if mtime > newest_mtime:
                newest_mtime = mtime

    if newest_mtime > 0:
        return datetime.fromtimestamp(newest_mtime, tz=timezone.utc).isoformat()
    return None


def find_new_files(
    telegram_dir: Path,
    existing_data: Dict,
    logger,
) -> List[Path]:
    """Find .txt files in telegram directory that aren't already in the dataset."""
    existing_names = get_existing_names(existing_data)
    existing_hashes = get_file_hashes(DATA_DIR)

    new_files = []
    skipped = 0

    if not telegram_dir.exists():
        logger.warning(f"Telegram presets directory not found: {telegram_dir}")
        return new_files

    txt_files = list(telegram_dir.rglob("*.txt"))
    logger.info(f"Found {len(txt_files)} .txt files in {telegram_dir}")

    for filepath in txt_files:
        # Check by name
        if filepath.stem in existing_names:
            skipped += 1
            logger.debug(f"  Skipping (duplicate name): {filepath.name}")
            continue

        # Check by content hash
        file_hash = compute_file_hash(filepath)
        if file_hash in existing_hashes:
            skipped += 1
            logger.debug(f"  Skipping (duplicate content): {filepath.name}")
            continue

        new_files.append(filepath)

    logger.info(f"New files to process: {len(new_files)} (skipped {skipped} duplicates)")
    return new_files


def resolve_tag_and_collection(filepath: Path) -> tuple:
    """
    Resolve the tag (Proven/Unproven) and collection hierarchy from the
    postprocessed directory structure.

    Expected structure after extract_and_postprocess.py:
      telegram_raw/
        Sp2UnofFILES1/
          extracted/
            Contact/
              preset1.txt
            Remote/
              preset2.txt
          postprocess_manifest.json
        s2_unof_unproven/
          extracted/
            Plasma/
              preset3.txt
          postprocess_manifest.json

    Returns (tag, relative_collection_path, group_slug)
    """
    parts = filepath.parts

    # Find the group slug (first directory under telegram_raw)
    try:
        telegram_raw_idx = parts.index("telegram_raw")
    except ValueError:
        return ("Telegram", str(filepath.parent), "unknown")

    group_slug = parts[telegram_raw_idx + 1] if len(parts) > telegram_raw_idx + 1 else "unknown"

    # Determine tag from group slug
    group_key = group_slug.lower().replace("_", "")
    tag = None
    for key, t in GROUP_TAG_MAP.items():
        if key in group_key or key.replace("_", "") in group_key:
            tag = t
            break
    if not tag:
        if "unof" in group_key or "unproven" in group_key:
            tag = "Unproven"
        else:
            tag = "Proven"

    # Find mode from the postprocessed directory structure
    # The file should be under telegram_raw/<group>/extracted/<mode>/file.txt
    try:
        extracted_idx = parts.index("extracted")
        if extracted_idx + 1 < len(parts):
            mode_or_file = parts[extracted_idx + 1]
            # Check if this is a mode directory
            if mode_or_file in ("Contact", "Remote", "Plasma", "Coil", "Scalar", "Laser", "Other"):
                collection = f"{tag}/{mode_or_file}"
            else:
                collection = tag
        else:
            collection = tag
    except ValueError:
        collection = tag

    return tag, collection, group_slug


def extract_from_files(
    files: List[Path],
    telegram_raw_dir: Path,
    parser: PresetParser,
    logger,
) -> List[Dict]:
    """Extract program data from a list of .txt files with proven/unproven tagging."""
    new_programs = []
    errors = []

    for filepath in files:
        try:
            tag, collection, group_slug = resolve_tag_and_collection(filepath)

            programs = parser.parse_file(filepath, collection)

            for prog in programs:
                prog_dict = prog.to_dict()
                prog_dict["source"] = "telegram"
                prog_dict["_source_file"] = str(filepath.name)
                prog_dict["_group"] = group_slug
                prog_dict["tag"] = tag
                # Ensure collection reflects the tag hierarchy
                prog_dict["collection"] = collection
                new_programs.append(prog_dict)
                logger.debug(f"  Extracted: {prog.name} (tag={tag}, collection={collection})")

        except Exception as e:
            errors.append((str(filepath), str(e)))
            logger.warning(f"  Error processing {filepath.name}: {e}")

    if errors:
        logger.warning(f"Failed to process {len(errors)} files:")
        for path, err in errors[:10]:
            logger.warning(f"  {path}: {err}")

    return new_programs


def merge_presets(
    existing_data: Dict,
    new_programs: List[Dict],
    logger,
) -> Dict:
    """Merge new programs into existing dataset."""
    merged = dict(existing_data)
    merged.setdefault("programs", [])

    # Track added
    existing_ids = {p["id"] for p in merged["programs"]}
    added = 0
    skipped = 0

    for prog in new_programs:
        # Assign new UUID if id conflicts
        if prog["id"] in existing_ids:
            prog["id"] = Program(
                id="", name="", description="", code="",
                frequencies=[], preset_file="", collection="", mode="Other"
            ).id  # Generate fresh UUID

        merged["programs"].append(prog)
        existing_ids.add(prog["id"])
        added += 1

    # Update metadata
    merged.setdefault("meta", {})
    merged["meta"]["last_merged"] = datetime.utcnow().isoformat()
    merged["meta"]["telegram_files_added"] = added
    merged["meta"]["total_programs"] = len(merged["programs"])

    logger.info(f"Merged {added} new programs into dataset")
    logger.info(f"Total programs: {merged['meta']['total_programs']}")

    return merged


def save_telegram_timestamps(telegram_raw_dir: Path, data_dir: Path, logger=None):
    """Save group update timestamps for the API server."""
    timestamps = {}

    if not telegram_raw_dir.exists():
        return timestamps

    for group_dir in sorted(telegram_raw_dir.iterdir()):
        if not group_dir.is_dir() or group_dir.name.startswith("."):
            continue

        ts = get_timestamp_for_group(group_dir)
        if ts:
            timestamps[group_dir.name] = ts
            if logger:
                logger.debug(f"  {group_dir.name}: last updated {ts}")

    timestamp_path = data_dir / "telegram_group_timestamps.json"
    with open(timestamp_path, "w", encoding="utf-8") as f:
        json.dump(timestamps, f, indent=2)

    if logger:
        logger.info(f"Saved timestamps for {len(timestamps)} groups: {timestamp_path}")
    return timestamps


def backup_existing():
    """Create a timestamped backup of the current presets_all.json."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"presets_all_backup_{timestamp}.json"
    shutil.copy2(PRESETS_ALL, backup_path)
    return backup_path


def save_merged(merged_data: Dict, output_path: Path):
    """Save merged data to output path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, indent=2, ensure_ascii=False)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Saved: {output_path} ({size_mb:.1f} MB)")


def reextract_all(output_dir: Path, clean: bool = False):
    """
    Re-extract everything from Wine prefix + postprocessed Telegram files.
    Uses the postprocessed directory structure with proven/unproven tags.
    """
    wine_presets = Path(__file__).parent.parent / "downloads" / "wine_spooky" / \
                   "drive_c" / "Spooky2" / "Preset Collections"

    if not wine_presets.exists() and not TELEGRAM_RAW_DIR.exists():
        print("ERROR: Neither Wine presets nor Telegram raw presets directory found.")
        print(f"  Expected: {wine_presets}")
        print(f"  Expected: {TELEGRAM_RAW_DIR}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    parser = PresetParser()
    all_programs = []
    stats = {
        "wine_files": 0,
        "telegram_files": 0,
        "total_programs": 0,
        "errors": 0,
    }

    # Extract from Wine prefix
    if wine_presets.exists():
        print(f"Extracting from Wine prefix: {wine_presets}")
        parser2 = PresetParser()
        for root, dirs, files in os.walk(wine_presets):
            root_path = Path(root)
            rel_path = root_path.relative_to(wine_presets)
            collection_name = str(rel_path)

            for txt_file in files:
                if not txt_file.lower().endswith(".txt"):
                    continue
                filepath = root_path / txt_file
                try:
                    programs = parser2.parse_file(filepath, collection_name)
                    for p in programs:
                        d = p.to_dict()
                        d["source"] = "wine"
                        all_programs.append(d)
                    stats["wine_files"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    print(f"  Error: {filepath}: {e}")

        print(f"  Extracted {stats['wine_files']} wine files")

    # Extract from postprocessed Telegram downloads
    if TELEGRAM_RAW_DIR.exists():
        print(f"Extracting from postprocessed Telegram: {TELEGRAM_RAW_DIR}")
        for filepath in TELEGRAM_RAW_DIR.rglob("*.txt"):
            try:
                tag, collection, group_slug = resolve_tag_and_collection(filepath)
                programs = parser.parse_file(filepath, collection)
                for p in programs:
                    d = p.to_dict()
                    d["source"] = "telegram"
                    d["_source_file"] = filepath.name
                    d["_group"] = group_slug
                    d["tag"] = tag
                    d["collection"] = collection
                    all_programs.append(d)
                stats["telegram_files"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"  Error: {filepath}: {e}")

        print(f"  Extracted {stats['telegram_files']} telegram files")

    # Build combined output
    stats["total_programs"] = len(all_programs)
    merged = {
        "meta": {
            "extracted_at": datetime.utcnow().isoformat(),
            "source": "combined:wine+telegram",
            "total_programs": len(all_programs),
            "stats": stats,
        },
        "programs": all_programs,
    }

    output_file = output_dir / "presets_all.json"
    save_merged(merged, output_file)

    # Also write stats
    stats_path = output_dir / "extraction_stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # Save Telegram group timestamps
    save_telegram_timestamps(TELEGRAM_RAW_DIR, output_dir)

    print(f"\nRe-extraction complete!")
    print(f"  Wine files processed:    {stats['wine_files']}")
    print(f"  Telegram files processed: {stats['telegram_files']}")
    print(f"  Total programs:          {stats['total_programs']}")
    print(f"  Errors:                  {stats['errors']}")
    print(f"  Output:                  {output_file}")

    return merged


def main():
    parser = argparse.ArgumentParser(
        description="Integrate Telegram-downloaded Spooky2 presets into the extraction pipeline"
    )
    parser.add_argument(
        "--config", "-c",
        default="scripts/telegram_config.env",
        help="Path to telegram config file (for reference)",
    )
    parser.add_argument(
        "--reextract",
        action="store_true",
        help="Re-extract from both Wine prefix and postprocessed Telegram files (full rebuild)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Used with --reextract: start fresh",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output path for merged JSON (default: data/presets/presets_all.json)",
    )
    parser.add_argument(
        "--telegram-dir", "-t",
        default=None,
        help="Path to postprocessed telegram presets directory (default: data/presets/telegram_raw)",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip creating backup of existing presets_all.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Setup paths
    global TELEGRAM_RAW_DIR, DATA_DIR, PRESETS_ALL

    if args.telegram_dir:
        TELEGRAM_RAW_DIR = Path(args.telegram_dir)
    if args.output:
        PRESETS_ALL = Path(args.output)
        DATA_DIR = PRESETS_ALL.parent

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    logger = logging.getLogger("integrate_telegram")

    # Full re-extract mode
    if args.reextract:
        output_dir = Path(args.output) if args.output else DATA_DIR
        result = reextract_all(output_dir, clean=args.clean)
        print(f"\nDone! {result['meta']['total_programs']} programs in {PRESETS_ALL}")
        return

    # Merge mode: integrate new Telegram files into existing dataset
    print("=" * 60)
    print("Telegram Preset Integration")
    print("=" * 60)

    # Load existing data
    existing = load_existing_presets()
    print(f"Loaded existing: {len(existing.get('programs', []))} programs")

    # Find new files in postprocessed directory
    new_files = find_new_files(TELEGRAM_RAW_DIR, existing, logger)

    if not new_files:
        print("\nNo new files to integrate. Dataset is up to date!")
        # Still update timestamps even if no new files
        save_telegram_timestamps(TELEGRAM_RAW_DIR, DATA_DIR, logger)
        return

    print(f"\nNew files to extract: {len(new_files)}")
    for f in new_files[:5]:
        tag, collection, group_slug = resolve_tag_and_collection(f)
        print(f"  - {f.name} -> [{tag}] {collection}")
    if len(new_files) > 5:
        print(f"  ... and {len(new_files) - 5} more")

    if args.dry_run:
        print("\n(Dry run - no changes made)")
        return

    # Backup existing
    if not args.skip_backup:
        backup_path = backup_existing()
        print(f"Backup created: {backup_path}")

    # Extract from new files
    print("\nExtracting from new files...")
    parser_obj = PresetParser()
    new_programs = extract_from_files(new_files, TELEGRAM_RAW_DIR, parser_obj, logger)

    if not new_programs:
        print("No programs extracted from new files.")
        return

    # Merge
    merged = merge_presets(existing, new_programs, logger)

    # Save
    save_merged(merged, PRESETS_ALL)

    # Save Telegram group timestamps
    save_telegram_timestamps(TELEGRAM_RAW_DIR, DATA_DIR, logger)

    print("\nIntegration complete!")
    print(f"  Programs added:   {len(new_programs)}")
    print(f"  Total programs:   {merged['meta']['total_programs']}")


if __name__ == "__main__":
    main()