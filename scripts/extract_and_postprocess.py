#!/usr/bin/env python3
"""
Extract and Postprocess Downloaded Telegram Presets
===================================================

Post-processes files downloaded by telegram_scraper.py:
1. Recursively extracts archives (.zip, .7z, .rar, nested zips) until
   everything is .txt files.
2. Tags files based on their source Telegram group:
   - @Sp2UnofFILES1 -> "Proven" collection
   - @s2_unof_unproven -> "Unproven" collection
3. Organizes into a tree hierarchy compatible with extract_presets.py:
   Proven/Contact/, Proven/Remote/, Proven/Plasma/, etc.
   Unproven/Contact/, Unproven/Remote/, Unproven/Plasma/, etc.
4. Detects mode (Contact/Remote/Plasma/etc.) from filenames and content.
5. Saves metadata about when each group was last updated.

Usage:
    python3 scripts/extract_and_postprocess.py
    python3 scripts/extract_and_postprocess.py --source ./downloads/telegram_presets
    python3 scripts/extract_and_postprocess.py --dry-run
"""

import os
import sys
import re
import json
import shutil
import zipfile
import subprocess
import tempfile
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Map group slugs to collection tags
GROUP_TAG_MAP = {
    "sp2unoffiles1": ("Proven", "Proven Files from Spooky2 Official Group"),
    "s2_unof_unproven": ("Unproven", "Unproven Presets from Spooky2 Community"),
}

# Archive extensions to extract
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".exe"}

# Maximum recursion depth for nested archives
MAX_EXTRACT_DEPTH = 10

# Maximum total extracted files before aborting
MAX_EXTRACTED_FILES = 50000


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging."""
    logger = logging.getLogger("extract_and_postprocess")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    return logger


# ---------------------------------------------------------------------------
# Archive extraction
# ---------------------------------------------------------------------------

def is_archive(filepath: Path) -> bool:
    """Check if a file is an archive we can extract."""
    suffix = filepath.suffix.lower()
    if suffix in ARCHIVE_EXTENSIONS:
        return True
    # Handle double extensions like .zip.exe
    name = filepath.name.lower()
    if name.endswith(".zip.exe") or name.endswith(".7z.exe"):
        return True
    return False


def extract_zip(filepath: Path, dest_dir: Path, logger: logging.Logger) -> int:
    """Extract a zip file. Returns number of files extracted."""
    count = 0
    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            for member in zf.namelist():
                # Skip directories
                if member.endswith("/"):
                    continue
                # Extract
                source = zf.open(member)
                # Sanitize target path (prevent path traversal)
                target_name = os.path.basename(member)
                if not target_name:
                    continue
                target_path = dest_dir / target_name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)
                count += 1
        logger.debug(f"  Extracted {count} files from zip: {filepath.name}")
    except (zipfile.BadZipFile, Exception) as e:
        logger.warning(f"  Failed to extract zip {filepath.name}: {e}")
    return count


def extract_7z(filepath: Path, dest_dir: Path, logger: logging.Logger) -> int:
    """Extract a 7z file using 7z command. Returns number of files extracted."""
    count = 0
    try:
        result = subprocess.run(
            ["7z", "x", str(filepath), f"-o{dest_dir}", "-y"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            # Count extracted files
            count = len([f for f in dest_dir.rglob("*") if f.is_file()])
            logger.debug(f"  Extracted {count} files from 7z: {filepath.name}")
        else:
            logger.warning(f"  7z extraction failed for {filepath.name}: {result.stderr}")
    except Exception as e:
        logger.warning(f"  Failed to extract 7z {filepath.name}: {e}")
    return count


def extract_rar(filepath: Path, dest_dir: Path, logger: logging.Logger) -> int:
    """Extract a rar file using unrar command. Returns number of files extracted."""
    count = 0
    try:
        result = subprocess.run(
            ["unrar", "x", "-y", str(filepath), str(dest_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            count = len([f for f in dest_dir.rglob("*") if f.is_file()])
            logger.debug(f"  Extracted {count} files from rar: {filepath.name}")
        else:
            logger.warning(f"  unrar extraction failed for {filepath.name}: {result.stderr}")
    except Exception as e:
        logger.warning(f"  Failed to extract rar {filepath.name}: {e}")
    return count


def extract_exe(filepath: Path, dest_dir: Path, logger: logging.Logger) -> int:
    """
    Attempt to extract an .exe installer using 7z (many installers are just zip-based).
    Returns number of files extracted.
    """
    count = 0
    try:
        # Try 7z extraction first (works for many InnoSetup/NSIS installers)
        result = subprocess.run(
            ["7z", "x", str(filepath), f"-o{dest_dir}", "-y"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            count = len([f for f in dest_dir.rglob("*") if f.is_file()])
            logger.debug(f"  Extracted {count} files from exe: {filepath.name}")
        else:
            logger.debug(f"  7z extraction of exe returned {result.returncode}: {filepath.name}")
    except Exception as e:
        logger.debug(f"  Could not extract exe {filepath.name}: {e}")
    return count


def extract_archive(filepath: Path, dest_dir: Path, logger: logging.Logger) -> int:
    """Extract an archive based on its type. Returns number of files extracted."""
    suffix = filepath.suffix.lower()
    name = filepath.name.lower()

    if suffix == ".zip" or name.endswith(".zip.exe"):
        return extract_zip(filepath, dest_dir, logger)
    elif suffix == ".7z" or name.endswith(".7z.exe"):
        return extract_7z(filepath, dest_dir, logger)
    elif suffix == ".rar":
        return extract_rar(filepath, dest_dir, logger)
    elif suffix == ".exe":
        return extract_exe(filepath, dest_dir, logger)
    else:
        logger.warning(f"  Unknown archive type: {filepath.name}")
        return 0


def recursive_extract(source_dir: Path, output_dir: Path, logger: logging.Logger) -> Dict:
    """
    Recursively extract all archives in source_dir.
    Returns stats dict.
    """
    stats = {
        "archives_processed": 0,
        "files_extracted": 0,
        "txt_files": 0,
        "errors": [],
    }

    # First, separate already-extracted .txt files from archives
    txt_files = list(source_dir.rglob("*.txt"))
    stats["txt_files"] = len(txt_files)

    # Find all archives
    archives = [f for f in source_dir.rglob("*") if f.is_file() and is_archive(f)]

    if not archives and txt_files:
        logger.info(f"  No archives to extract, {len(txt_files)} .txt files already present")
        return stats

    logger.info(f"  Found {len(archives)} archives to extract, {len(txt_files)} existing .txt files")

    # Create temp working directory for extraction
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        work_dir = tmpdir / "extract"
        work_dir.mkdir()

        # Copy non-archive files first
        for txt_file in txt_files:
            rel = txt_file.relative_to(source_dir)
            dest = work_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(txt_file, dest)

        # Extract all archives into work_dir
        for archive in archives:
            logger.info(f"  Extracting: {archive.name}")
            try:
                count = extract_archive(archive, work_dir, logger)
                stats["archives_processed"] += 1
                stats["files_extracted"] += count
            except Exception as e:
                error_msg = f"{archive.name}: {e}"
                stats["errors"].append(error_msg)
                logger.warning(f"  Error extracting {archive.name}: {e}")

        # Now recursively find and extract any nested archives
        depth = 0
        while depth < MAX_EXTRACT_DEPTH:
            nested_archives = [
                f for f in work_dir.rglob("*")
                if f.is_file() and is_archive(f)
            ]
            if not nested_archives:
                break

            logger.info(f"  Depth {depth + 1}: Found {len(nested_archives)} nested archives")
            for archive in nested_archives:
                # Extract into same directory as the archive
                count = extract_archive(archive, archive.parent, logger)
                stats["archives_processed"] += 1
                stats["files_extracted"] += count
                try:
                    archive.unlink()  # Remove the archive after extraction
                except Exception:
                    pass

            depth += 1

        if depth >= MAX_EXTRACT_DEPTH:
            logger.warning(f"  Reached maximum extraction depth ({MAX_EXTRACT_DEPTH})")

        # Count final txt files
        final_txts = list(work_dir.rglob("*.txt"))
        stats["txt_files"] = len(final_txts)
        logger.info(f"  Total .txt files after extraction: {stats['txt_files']}")

        # Copy all .txt files to output directory, preserving structure
        for txt_file in final_txts:
            rel = txt_file.relative_to(work_dir)
            dest = output_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(txt_file, dest)

        # Check file count limit
        total = len(list(output_dir.rglob("*.txt")))
        if total > MAX_EXTRACTED_FILES:
            logger.warning(f"  Warning: {total} files exceeds MAX_EXTRACTED_FILES ({MAX_EXTRACTED_FILES})")

    return stats


# ---------------------------------------------------------------------------
# Mode detection from filename/content
# ---------------------------------------------------------------------------

MODE_KEYWORDS = {
    "contact": "Contact",
    "remote": "Remote",
    "plasma": "Plasma",
    "coil": "Coil",
    "scalar": "Scalar",
    "laser": "Laser",
}


def detect_mode_from_filename(filename: str) -> Optional[str]:
    """Try to detect mode from filename."""
    name_lower = filename.lower()
    for keyword, mode in MODE_KEYWORDS.items():
        if keyword in name_lower:
            return mode
    return None


def detect_mode_from_content(filepath: Path, logger: logging.Logger) -> Optional[str]:
    """Try to detect mode from file content keywords."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(4096).lower()

        # Check for mode indicators in content
        # (P), (R), (C), (L), (S), (M) markers
        if "(p)" in content or "(plasma)" in content:
            return "Plasma"
        if "(r)" in content or "(remote)" in content:
            return "Remote"
        if "(c)" in content or "(contact)" in content:
            return "Contact"
        if "(l)" in content or "(cl)" in content or "(laser)" in content:
            return "Laser"
        if "(s)" in content or "(scalar)" in content:
            return "Scalar"
        if "(coil)" in content or "(m)" in content or "pemf" in content:
            return "Coil"

        # Prefix codes
        for prefix in ["rx ", "rx\t", "(rx)"]:
            if prefix in content:
                return "Remote"
        for prefix in ["px ", "px\t", "(px)"]:
            if prefix in content:
                return "Plasma"
        for prefix in ["cx ", "cx\t", "(cx)"]:
            return "Contact"
        for prefix in ["sx ", "sx\t", "(sx)"]:
            return "Scalar"
        for prefix in ["lx ", "lx\t", "(lx)"]:
            return "Laser"
        for prefix in ["mx ", "mx\t", "(mx)"]:
            return "Coil"

    except Exception as e:
        logger.debug(f"  Could not read content of {filepath.name}: {e}")

    return None


# ---------------------------------------------------------------------------
# File organization
# ---------------------------------------------------------------------------

def organize_files(
    source_dir: Path,
    output_base: Path,
    tag: str,
    description: str,
    logger: logging.Logger,
) -> Dict:
    """
    Organize extracted .txt files into collection hierarchy.
    Returns stats dict.
    """
    tag_dir = output_base / tag
    tag_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "tag": tag,
        "description": description,
        "total_files": 0,
        "organized_by_mode": {},
        "unclassified": 0,
    }

    txt_files = list(source_dir.rglob("*.txt"))

    for filepath in txt_files:
        stats["total_files"] += 1

        # Detect mode from filename first, then content
        mode = detect_mode_from_filename(filepath.stem)
        if not mode:
            mode = detect_mode_from_content(filepath, logger)

        if mode:
            mode_dir = tag_dir / mode
            mode_dir.mkdir(parents=True, exist_ok=True)
            dest = mode_dir / filepath.name

            stats["organized_by_mode"][mode] = stats["organized_by_mode"].get(mode, 0) + 1
        else:
            # Put unclassified files in root of tag directory
            dest = tag_dir / filepath.name
            stats["unclassified"] += 1

        if dest.exists():
            # Handle duplicates by appending number
            stem = dest.stem
            suffix = dest.suffix
            counter = 1
            while dest.exists():
                dest = dest.parent / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.copy2(filepath, dest)

    return stats


# ---------------------------------------------------------------------------
# Metadata / timestamps
# ---------------------------------------------------------------------------

def save_group_timestamps(
    group_timestamps: Dict[str, datetime],
    output_dir: Path,
    logger: logging.Logger,
):
    """Save group update timestamps to a JSON file accessible by the API."""
    timestamp_path = output_dir / "telegram_group_timestamps.json"

    data = {}
    for group_slug, ts in group_timestamps.items():
        data[group_slug] = {
            "last_updated": ts.isoformat(),
            "last_updated_unix": ts.timestamp(),
        }

    with open(timestamp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info(f"  Timestamps saved: {timestamp_path}")


def get_group_scrape_time(group_slug: str, output_dir: Path) -> Optional[datetime]:
    """Get the last scrape time for a group from progress.json."""
    progress_path = output_dir / group_slug / "progress.json"

    if not progress_path.exists():
        return None

    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Use the file modification time of progress.json as the scrape time
        mtime = progress_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Post-process Telegram-downloaded Spooky2 preset files",
        epilog="""
Examples:
  # Process default directories
  python3 extract_and_postprocess.py

  # Specify source directory
  python3 extract_and_postprocess.py --source ./downloads/telegram_presets

  # Dry run (show what would be done)
  python3 extract_and_postprocess.py --dry-run

  # Use specific output directory
  python3 extract_and_postprocess.py --output ./data/presets/telegram_raw
        """,
    )

    parser.add_argument(
        "--source", "-s",
        default=None,
        help="Source directory with Telegram downloads (default: downloads/telegram_presets)",
    )
    parser.add_argument(
        "--output", "-o",
        default="data/presets/telegram_raw",
        help="Output directory for organized files (default: data/presets/telegram_raw)",
    )
    parser.add_argument(
        "--manifest-dir",
        default=None,
        help="Directory with scraper manifests (default: same as source)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    logger = setup_logging("DEBUG" if args.verbose else "INFO")

    # Resolve paths
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent

    source_dir = Path(args.source) if args.source else root_dir / "downloads" / "telegram_presets"
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = root_dir / "data" / "presets" / "telegram_raw"
    manifest_dir = Path(args.manifest_dir) if args.manifest_dir else source_dir

    if not source_dir.exists():
        logger.error(f"Source directory not found: {source_dir}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Spooky2 Telegram Preset Post-Processor")
    logger.info("=" * 60)
    logger.info(f"Source directory: {source_dir.resolve()}")
    logger.info(f"Output directory: {output_dir.resolve()}")
    logger.info(f"Dry run: {args.dry_run}")

    overall_stats = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "groups_processed": [],
        "total_files": 0,
        "total_archives_extracted": 0,
    }

    group_timestamps = {}

    # Process each group directory
    for group_slug in sorted(source_dir.iterdir()):
        if not group_slug.is_dir() or group_slug.name.startswith("."):
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing group: {group_slug.name}")
        logger.info(f"{'='*60}")

        # Determine tag from group name
        tag = None
        description = None
        group_key = group_slug.name.lower().replace("_", "")

        for key, (t, d) in GROUP_TAG_MAP.items():
            if key in group_key or key.replace("_", "") in group_key:
                tag = t
                description = d
                break

        if not tag:
            # Try to match by directory name patterns
            if "unof" in group_key or "unproven" in group_key:
                tag = "Unproven"
                description = "Unproven Presets"
            elif "file" in group_key or "proven" in group_key:
                tag = "Proven"
                description = "Proven Presets"
            else:
                tag = "Telegram"
                description = f"Presets from {group_slug.name}"

            logger.info(f"  Auto-detected tag: {tag}")
        else:
            logger.info(f"  Tag: {tag} - {description}")

        # Get timestamp from progress.json
        scrape_time = get_group_scrape_time(group_slug.name, source_dir)
        if scrape_time:
            group_timestamps[group_slug.name] = scrape_time
            logger.info(f"  Last scraped: {scrape_time.isoformat()}")

        # Extract archives
        extract_dest = output_dir / group_slug.name / "extracted"
        if not args.dry_run:
            extract_dest.mkdir(parents=True, exist_ok=True)

            stats = recursive_extract(group_slug, extract_dest, logger)
            overall_stats["total_archives_extracted"] += stats["archives_processed"]

            if stats["errors"]:
                overall_stats["groups_processed"].append({
                    "name": group_slug.name,
                    "tag": tag,
                    "errors": stats["errors"],
                })
                logger.warning(f"  Errors: {len(stats['errors'])}")
        else:
            # Dry run: just count
            txt_count = len(list(group_slug.rglob("*.txt")))
            archive_count = len([f for f in group_slug.rglob("*") if f.is_file() and is_archive(f)])
            logger.info(f"  Dry run: {txt_count} .txt files, {archive_count} archives")
            stats = {"txt_files": txt_count, "archives_processed": archive_count}

        # Organize into tag/mode hierarchy
        if not args.dry_run and stats["txt_files"] > 0:
            org_stats = organize_files(
                extract_dest,
                output_dir / group_slug.name,
                tag,
                description,
                logger,
            )
            logger.info(f"  Organized: {org_stats['total_files']} files")
            for mode, count in org_stats["organized_by_mode"].items():
                logger.info(f"    {mode}: {count} files")
            if org_stats["unclassified"] > 0:
                logger.info(f"    Unclassified: {org_stats['unclassified']} files")

            overall_stats["groups_processed"].append({
                "name": group_slug.name,
                "tag": tag,
                "description": description,
                "total_files": org_stats["total_files"],
                "organized_by_mode": org_stats["organized_by_mode"],
                "unclassified": org_stats["unclassified"],
            })
            overall_stats["total_files"] += org_stats["total_files"]

        # Save per-group manifest
        if not args.dry_run:
            group_manifest = output_dir / group_slug.name / "postprocess_manifest.json"
            with open(group_manifest, "w", encoding="utf-8") as f:
                json.dump(org_stats, f, indent=2, default=str)
            logger.info(f"  Manifest saved: {group_manifest}")

    # Save group timestamps
    if not args.dry_run and group_timestamps:
        save_group_timestamps(group_timestamps, output_dir, logger)
        # Also save to the presets root for the API server
        save_group_timestamps(group_timestamps, root_dir / "data" / "presets", logger)

    # Save overall manifest
    overall_path = output_dir / "postprocess_manifest.json"
    overall_stats["completed_at"] = datetime.now(timezone.utc).isoformat()

    if not args.dry_run:
        with open(overall_path, "w", encoding="utf-8") as f:
            json.dump(overall_stats, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"\nOverall manifest saved: {overall_path}")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("POST-PROCESSING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Groups processed:      {len(overall_stats['groups_processed'])}")
    logger.info(f"Archives extracted:    {overall_stats['total_archives_extracted']}")
    logger.info(f"Total .txt files:      {overall_stats['total_files']}")
    logger.info(f"Timestamped groups:    {len(group_timestamps)}")
    logger.info(f"Output directory:      {output_dir.resolve()}")
    logger.info(f"Completed at:          {overall_stats['completed_at']}")

    return overall_stats


if __name__ == "__main__":
    main()