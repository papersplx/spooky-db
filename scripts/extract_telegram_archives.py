#!/usr/bin/env python3
"""
Extract Telegram archive containers (.zip.txt, .rar.txt, .zip, .rar) from
downloads/telegram_presets into data/presets/telegram_raw with mode subfolders.
Builds and maintains a persistent exclusion list for archives that contain no .txt presets.
"""

import subprocess, tempfile, shutil, json, logging, os
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

SOURCE_ROOT = Path('downloads/telegram_presets')
DEST_ROOT = Path('data/presets/telegram_raw')
EXCLUSION_FILE = Path('scripts/telegram_exclusions.json')

# Known mode keywords used in folder names and filenames
MODE_KEYWORDS = {
    'contact': 'Contact',
    'remote': 'Remote',
    'plasma': 'Plasma',
    'coil': 'Coil',
    'scalar': 'Scalar',
    'laser': 'Laser',
}

def load_exclusions():
    if EXCLUSION_FILE.exists():
        with open(EXCLUSION_FILE) as f:
            data = json.load(f)
            return set(data)
    return set()

def save_exclusions(excl):
    with open(EXCLUSION_FILE, 'w') as f:
        json.dump(sorted(list(excl)), f, indent=2)

def is_archive(p: Path) -> bool:
    """Return true if file is a known archive type (including .zip.txt, .rar.txt)."""
    suff = p.suffix.lower()
    if suff in {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.Z', '.lzma', '.lz', '.zst', '.tzst',
                '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz', '.tar.Z', '.taz', '.tar.lzma',
                '.tlz', '.tar.zst', '.tzst'}:
        return True
    name = p.name.lower()
    if name.endswith('.zip.txt') or name.endswith('.rar.txt') or name.endswith('.7z.txt'):
        return True
    return False

def detect_mode_from_parts(parts):
    """Given a sequence of path parts, return the first matching mode string or None."""
    for part in parts:
        low = part.lower()
        if low in MODE_KEYWORDS:
            return MODE_KEYWORDS[low]
    return None

def extract_archive_recursive(archive: Path, dest_dir: Path) -> int:
    """
    Recursively extract an archive (and any nested archives) using 7z.
    Copies all resulting .txt files (that are not themselves archives) into dest_dir.
    Returns number of .txt files added.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        # Copy archive into work to avoid modifying original
        shutil.copy2(archive, work / archive.name)

        # Iteratively extract any archives present
        while True:
            # Find all archive files within work tree
            archs = [p for p in work.rglob('*') if p.is_file() and is_archive(p)]
            if not archs:
                break
            for a in list(archs):
                try:
                    subprocess.run(['7z', 'x', '-o' + str(a.parent), '-y', str(a)],
                                   check=True, capture_output=True)
                    a.unlink()  # remove the archive after extraction
                except subprocess.CalledProcessError as e:
                    logger.error(f"  Extraction error for {a}: {e}")
                    # Remove problematic archive to avoid infinite loop and continue with others
                    try:
                        a.unlink()
                    except Exception:
                        pass
                    continue  # skip to next archive

        # Collect all .txt files that are not archives
        txts = [p for p in work.rglob('*.txt') if not is_archive(p)]
        added = 0
        for txt in txts:
            target = dest_dir / txt.name
            if target.exists():
                stem = txt.stem
                suffix = txt.suffix
                i = 1
                while True:
                    target = dest_dir / f"{stem}_{i}{suffix}"
                    if not target.exists():
                        break
                    i += 1
            shutil.copy2(txt, target)
            added += 1
        return added

def main():
    DEST_ROOT.mkdir(parents=True, exist_ok=True)

    # Clean dest except top-level timestamps file
    for item in DEST_ROOT.iterdir():
        if item.name == 'telegram_group_timestamps.json':
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    groups = ['Spooky2_PROVEN_FILES', 'Spooky2_Unproven']
    exclusions = load_exclusions()
    stats = {'archives_processed': 0, 'txt_files': 0, 'skipped': 0}

    for group in groups:
        src_group = SOURCE_ROOT / group
        if not src_group.exists():
            logger.warning(f"Source group not found: {src_group}")
            continue
        dest_group = DEST_ROOT / group / 'extracted'
        dest_group.mkdir(parents=True, exist_ok=True)

        logger.info(f"\nProcessing group: {group}")

        # Step 1: copy direct non-archive .txt files
        for root, dirs, files in os.walk(src_group):
            root_path = Path(root)
            try:
                rel_to_group = root_path.relative_to(src_group)
            except ValueError:
                continue
            mode = detect_mode_from_parts(rel_to_group.parts)
            dest_base = dest_group / mode if mode else dest_group
            dest_base.mkdir(parents=True, exist_ok=True)

            for f in files:
                fpath = root_path / f
                if is_archive(fpath):
                    continue
                # It's a direct .txt file (non-archive). Copy.
                dest_file = dest_base / f
                if dest_file.exists():
                    stem = Path(f).stem
                    suffix = Path(f).suffix
                    i = 1
                    while True:
                        dest_file = dest_base / f"{stem}_{i}{suffix}"
                        if not dest_file.exists():
                            break
                        i += 1
                shutil.copy2(fpath, dest_file)
                stats['txt_files'] += 1

        # Step 2: process archives
        for root, dirs, files in os.walk(src_group):
            root_path = Path(root)
            try:
                rel_to_group = root_path.relative_to(src_group)
            except ValueError:
                continue
            mode = detect_mode_from_parts(rel_to_group.parts)
            dest_base = dest_group / mode if mode else dest_group
            dest_base.mkdir(parents=True, exist_ok=True)

            for f in files:
                fpath = root_path / f
                if not is_archive(fpath):
                    continue

                if str(fpath) in exclusions:
                    logger.info(f"Skipping excluded archive: {fpath.name}")
                    stats['skipped'] += 1
                    continue

                logger.info(f"Extracting archive: {fpath.name} (mode={mode})")
                before = len(list(dest_base.glob('*.txt')))
                added = extract_archive_recursive(fpath, dest_base)
                after = len(list(dest_base.glob('*.txt')))

                if added == 0 and after <= before:
                    logger.warning(f"  No .txt files extracted from {fpath.name}, adding to exclusions")
                    exclusions.add(str(fpath))
                    stats['skipped'] += 1
                else:
                    stats['archives_processed'] += 1
                    stats['txt_files'] += added

    # Save exclusions
    save_exclusions(exclusions)

    # Write per-group postprocess_manifest.json
    now_iso = datetime.now(timezone.utc).isoformat()
    for group in groups:
        manifest = DEST_ROOT / group / 'postprocess_manifest.json'
        with open(manifest, 'w') as f:
            json.dump({"completed_at": now_iso, "total_files": 0, "organized_by_mode": {}}, f, indent=2)

    # Update top-level telegram_group_timestamps.json
    top_stamps = {}
    for group in groups:
        extracted_dir = DEST_ROOT / group / 'extracted'
        latest_ts = now_iso
        if extracted_dir.exists():
            mtimes = [p.stat().st_mtime for p in extracted_dir.rglob('*') if p.is_file()]
            if mtimes:
                latest_ts = datetime.fromtimestamp(max(mtimes), tz=timezone.utc).isoformat()
        top_stamps[group] = latest_ts
    with open(DEST_ROOT / 'telegram_group_timestamps.json', 'w') as f:
        json.dump(top_stamps, f, indent=2)

    logger.info(f"\nExtraction complete:")
    logger.info(f"  Archives processed: {stats['archives_processed']}")
    logger.info(f"  .txt files extracted: {stats['txt_files']}")
    logger.info(f"  Skipped (excluded): {stats['skipped']}")
    logger.info(f"  Exclusions written to {EXCLUSION_FILE}")

if __name__ == '__main__':
    main()
