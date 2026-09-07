#!/usr/bin/env python3
"""
Prepare Spooky2 preset files for NotebookLM upload.

NotebookLM has a 200MB file size limit. This script groups the by_collection
JSON files into logical categories, each under 200MB, and outputs them to
downloads/notebooklm/ for manual upload to a file hosting service.

Usage:
    python3 scripts/prepare_notebooklm_uploads.py [--max-size MB] [--check] [--force]

Options:
    --max-size MB   Maximum file size per category (default: 200)
    --check         Verify existing files match manifest without regenerating
    --force         Force regeneration even if files already exist
"""

import json
import os
import sys
import argparse
import fnmatch
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
BY_COLLECTION_DIR = BASE_DIR / "data" / "presets" / "by_collection"
OUTPUT_DIR = BASE_DIR / "downloads" / "notebooklm"
MANIFEST_PATH = BASE_DIR / "spooky2-search" / "public" / "data" / "notebooklm-manifest.json"

# NotebookLM limit
MAX_SIZE_MB = 200
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

# Category definitions: name -> list of glob patterns
CATEGORIES = {
    "Cancer & Oncology": [
        "Cancer.json",
        "Cancer_*.json",
        "Factory_Cancer_*.json",
        "Factory_HIV_*.json",
    ],
    "DNA & Pathogens": [
        "DNA_*.json",
    ],
    "JW Peptides": [
        "JW_Peptides*.json",
    ],
    "Detox & Terrain": [
        "Detox.json",
        "Detox_*.json",
        "Environmental.json",
        "Environmental_*.json",
    ],
    "Healing & Wellness": [
        "Heal.json",
        "Heal_*.json",
        "Biofeedback*.json",
        "Frequency Sweeps*.json",
    ],
    "Morgellons & Lyme": [
        "Morgellons*.json",
    ],
    "Miscellaneous & Other": [
        "Miscellaneous*.json",
        "Factory_*.json",
        "Radionics.json",
        "Shell*.json",
        "COVID-19*.json",
    ],
}


def glob_to_files(pattern: str, all_files: list) -> list:
    """Match files by glob pattern."""
    return [f for f in all_files if fnmatch.fnmatch(f.name, pattern)]


def merge_json_files(files: list) -> list:
    """Merge multiple JSON preset files into a single list."""
    merged = []
    for f in sorted(files):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    merged.extend(data)
                elif isinstance(data, dict) and "programs" in data:
                    merged.extend(data["programs"])
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Warning: Could not read {f.name}: {e}")
    return merged


def validate_json_file(path: Path) -> bool:
    """Validate that a JSON file is properly formatted and loadable."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            print(f"    WARNING: {path.name} is not a JSON array")
            return False
        if len(data) == 0:
            print(f"    WARNING: {path.name} is empty")
            return False
        # Check first item has expected structure
        first = data[0]
        if not isinstance(first, dict):
            print(f"    WARNING: {path.name} items are not objects")
            return False
        return True
    except json.JSONDecodeError as e:
        print(f"    ERROR: {path.name} is invalid JSON: {e}")
        return False
    except IOError as e:
        print(f"    ERROR: Could not read {path.name}: {e}")
        return False


def check_existing(manifest_path: Path, output_dir: Path) -> bool:
    """Verify existing files match manifest. Returns True if all OK."""
    if not manifest_path.exists():
        print("No manifest found. Run without --check to generate files.")
        return False

    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading manifest: {e}")
        return False

    if not manifest.get("categories"):
        print("Manifest has no categories. Run without --check to regenerate.")
        return False

    all_ok = True
    for cat in manifest["categories"]:
        file_path = output_dir / cat["file"]
        if not file_path.exists():
            print(f"  MISSING: {cat['file']}")
            all_ok = False
        else:
            actual_size = file_path.stat().st_size / 1024 / 1024
            expected_size = cat.get("size_mb", 0)
            # Allow 10% tolerance for size comparison
            if expected_size > 0 and abs(actual_size - expected_size) / expected_size > 0.1:
                print(f"  SIZE MISMATCH: {cat['file']} (expected ~{expected_size}MB, got {actual_size:.1f}MB)")
                all_ok = False
            else:
                print(f"  OK: {cat['file']} ({actual_size:.1f}MB)")

    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Prepare Spooky2 preset files for NotebookLM upload"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=200,
        help="Maximum file size per category in MB (default: 200)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify existing files match manifest without regenerating"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if files already exist"
    )
    args = parser.parse_args()

    # Base paths
    base_dir = Path(__file__).resolve().parent.parent
    by_collection_dir = base_dir / "data" / "presets" / "by_collection"
    output_dir = base_dir / "downloads" / "notebooklm"
    manifest_path = base_dir / "spooky2-search" / "public" / "data" / "notebooklm-manifest.json"

    max_size_mb = args.max_size
    max_size_bytes = max_size_mb * 1024 * 1024

    # Handle --check mode
    if args.check:
        print("Checking existing files against manifest...")
        if check_existing(manifest_path, output_dir):
            print("\nAll files verified successfully!")
        else:
            print("\nSome issues found. Run without --check to regenerate.")
            sys.exit(1)
        return

    # Get all collection files
    all_files = sorted(by_collection_dir.glob("*.json"))
    if not all_files:
        print(f"No JSON files found in {by_collection_dir}")
        return

    # Check if files already exist
    if output_dir.exists() and any(output_dir.glob("*.json")) and not args.force:
        print("Output files already exist. Use --force to regenerate or --check to verify.")
        return

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_for": "NotebookLM",
        "max_file_size_mb": max_size_mb,
        "categories": []
    }

    used_files = set()

    print(f"Processing {len(all_files)} collection files (max {max_size_mb}MB per file)...")
    print()

    for category_name, patterns in CATEGORIES.items():
        # Find matching files
        matched_files = []
        for pattern in patterns:
            matched_files.extend(glob_to_files(pattern, all_files))

        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in matched_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
        matched_files = unique_files

        if not matched_files:
            print(f"  {category_name}: No files matched, skipping")
            continue

        # Track used files
        used_files.update(matched_files)

        # Calculate total size
        total_size = sum(f.stat().st_size for f in matched_files)

        # Merge and write
        print(f"  {category_name}: {len(matched_files)} files, {total_size / 1024 / 1024:.1f} MB")

        if total_size > max_size_bytes:
            print(f"    WARNING: Category exceeds {max_size_mb}MB limit! Splitting required.")
            # Split into chunks
            chunks = []
            current_chunk = []
            current_size = 0

            for f in matched_files:
                fsize = f.stat().st_size
                if current_size + fsize > max_size_bytes * 0.9 and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0
                current_chunk.append(f)
                current_size += fsize

            if current_chunk:
                chunks.append(current_chunk)

            for i, chunk in enumerate(chunks, 1):
                suffix = f"_part{i}" if len(chunks) > 1 else ""
                output_name = f"{category_name.replace(' ', '_').replace('&', 'and')}{suffix}.json"
                output_path = output_dir / output_name

                merged = merge_json_files(chunk)
                chunk_size = sum(f.stat().st_size for f in chunk)

                with open(output_path, "w", encoding="utf-8") as fh:
                    json.dump(merged, fh, ensure_ascii=False, separators=(",", ":"))

                # Validate the written file
                if not validate_json_file(output_path):
                    print(f"    ERROR: Validation failed for {output_name}")
                    continue

                print(f"    Part {i}: {len(chunk)} files, {chunk_size / 1024 / 1024:.1f} MB -> {output_name}")

                manifest["categories"].append({
                    "name": f"{category_name} (Part {i})" if len(chunks) > 1 else category_name,
                    "file": output_name,
                    "size_mb": round(chunk_size / 1024 / 1024, 1),
                    "program_count": len(merged),
                    "source_files": [f.name for f in chunk],
                    "download_url": ""
                })
        else:
            # Single file for category
            output_name = f"{category_name.replace(' ', '_').replace('&', 'and')}.json"
            output_path = output_dir / output_name

            merged = merge_json_files(matched_files)

            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(merged, fh, ensure_ascii=False, separators=(",", ":"))

            # Validate the written file
            if not validate_json_file(output_path):
                print(f"    ERROR: Validation failed for {output_name}")
                continue

            actual_size = output_path.stat().st_size
            print(f"    -> {output_name} ({actual_size / 1024 / 1024:.1f} MB, {len(merged)} programs)")

            manifest["categories"].append({
                "name": category_name,
                "file": output_name,
                "size_mb": round(actual_size / 1024 / 1024, 1),
                "program_count": len(merged),
                "source_files": [f.name for f in matched_files],
                "download_url": ""
            })

    # Check for unused files
    unused = set(all_files) - used_files
    if unused:
        print(f"\n  {len(unused)} files not included in any category:")
        for f in sorted(unused):
            print(f"    - {f.name}")

    # Write manifest
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    print(f"\nManifest written to: {manifest_path}")
    print(f"Output files in: {output_dir}")
    print(f"\nNext steps:")
    print(f"  1. Upload files from {output_dir} to your file hosting service")
    print(f"  2. Update download_url fields in {manifest_path}")
    print(f"  3. Redeploy the website")


if __name__ == "__main__":
    main()
