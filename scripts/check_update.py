#!/usr/bin/env python3
"""
Check for new/updated preset files using MD5 hashes.
Compares current file hashes with cached hashes from previous extraction.
"""
import os
import sys
import hashlib
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
DATA_DIR = PROJECT_ROOT / "data" / "presets"
WINE_PREFIX = DOWNLOADS_DIR / "wine_spooky"
HASH_FILE = DATA_DIR / "file_hashes.txt"
EXTRACTION_STATS = DATA_DIR / "extraction_stats.json"

def find_preset_source():
    """Find the preset source directory."""
    # Check Wine prefix first
    wine_presets = WINE_PREFIX / "drive_c" / "Spooky2" / "Preset Collections"
    if wine_presets.exists():
        return wine_presets
    
    # Check temp directory
    tmp_presets = PROJECT_ROOT / "tmp" / "spooky2_presets" / "Preset Collections"
    if tmp_presets.exists():
        return tmp_presets
    
    print("ERROR: No preset source found.")
    print(f"Checked:")
    print(f"  - {wine_presets}")
    print(f"  - {tmp_presets}")
    sys.exit(1)

def calculate_hashes(preset_dir):
    """Calculate MD5 hashes for all .txt files in parallel."""
    print(f"Calculating MD5 hashes of preset files in {preset_dir}...")
    
    # Use find with xargs for parallel execution
    cmd = [
        'find', str(preset_dir), '-name', '*.txt', '-type', 'f', '-print0',
        '|', 'xargs', '-0', '-P', str(os.cpu_count() or 4),
        'md5sum'
    ]
    
    result = subprocess.run(
        ' '.join(cmd),
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"ERROR calculating hashes: {result.stderr}")
        sys.exit(1)
    
    # Parse and sort by filename
    lines = result.stdout.strip().split('\\n')
    # Sort by filename (second column)
    lines.sort(key=lambda x: x.split('  ', 1)[1] if '  ' in x else x)
    
    return lines

def load_cached_hashes():
    """Load previously stored hashes."""
    if not HASH_FILE.exists():
        return {}
    
    hashes = {}
    with open(HASH_FILE) as f:
        for line in f:
            line = line.strip()
            if '  ' in line:
                hash_val, filepath = line.split('  ', 1)
                hashes[filepath.strip()] = hash_val
    return hashes

def compare_hashes(current_hashes):
    """Compare current hashes with cached hashes."""
    current_dict = {}
    for line in current_hashes:
        if '  ' in line:
            hash_val, filepath = line.split('  ', 1)
            current_dict[filepath.strip()] = hash_val
    
    cached = load_cached_hashes()
    
    new_files = []
    modified_files = []
    deleted_files = []
    
    # Check for new/modified
    for filepath, hash_val in current_dict.items():
        if filepath not in cached:
            new_files.append(filepath)
        elif cached[filepath] != hash_val:
            modified_files.append(filepath)
    
    # Check for deleted
    for filepath in cached:
        if filepath not in current_dict:
            deleted_files.append(filepath)
    
    return new_files, modified_files, deleted_files

def main():
    print("=== Spooky2 Data Update Check (MD5-based) ===\n")
    
    # Find preset source
    preset_source = find_preset_source()
    print(f"Found presets at: {preset_source}\n")
    
    # Calculate current hashes
    current_hashes = calculate_hashes(preset_source)
    total_files = len(current_hashes)
    print(f"Found {total_files} preset files.\n")
    
    # Compare with cached hashes
    if HASH_FILE.exists():
        print("Comparing with stored hashes...\n")
        new_files, modified_files, deleted_files = compare_hashes(current_hashes)
        
        print("Results:")
        print(f"  New files: {len(new_files)}")
        print(f"  Modified files: {len(modified_files)}")
        print(f"  Deleted files: {len(deleted_files)}")
        
        total_changes = len(new_files) + len(modified_files) + len(deleted_files)
        
        if total_changes > 0:
            print("\nDetails:")
            for f in new_files[:5]:
                print(f"  NEW: {Path(f).name}")
            for f in modified_files[:5]:
                print(f"  MODIFIED: {Path(f).name}")
            if len(new_files) > 5:
                print(f"  ... and {len(new_files) - 5} more new files")
            if len(modified_files) > 5:
                print(f"  ... and {len(modified_files) - 5} more modified files")
            
            response = input("\nRe-extract presets? (y/N) ")
            if response.lower().startswith('y'):
                print("\nRunning extraction...")
                import shutil
                from datetime import datetime
                
                # Run extraction
                extract_script = SCRIPT_DIR / "extract_presets.py"
                cmd = [
                    'python3', str(extract_script),
                    str(preset_source),
                    '--output', str(DATA_DIR)
                ]
                result = subprocess.run(cmd, cwd=PROJECT_ROOT)
                
                if result.returncode == 0:
                    print("\nUpdating hash file...")
                    with open(HASH_FILE, 'w') as f:
                        f.write('\\n'.join(current_hashes))
                    
                    print("Copying to search app...")
                    src = DATA_DIR / "presets_all.json"
                    dst = PROJECT_ROOT / "spooky2-search" / "public" / "data" / "presets_all.json"
                    if src.exists():
                        shutil.copy2(src, dst)
                    
                    print("Rebuilding search app...")
                    build_cmd = ['cd', str(PROJECT_ROOT / "spooky2-search"), '&&', 'npm', 'run', 'build']
                    subprocess.run(' '.join(build_cmd), shell=True)
                    
                    print("\nDone! Data updated.")
                else:
                    print("ERROR: Extraction failed.")
            else:
                print("\nSkipped re-extraction.")
        else:
            print("\nNo changes detected. Data is up-to-date.")
    else:
        print("No stored hashes found. This appears to be the first run.\n")
        print("Storing current hashes...")
        with open(HASH_FILE, 'w') as f:
            f.write('\\n'.join(current_hashes))
        print(f"Hash file created at: {HASH_FILE}")
        print("\nRun the script again after making changes to detect updates.")
    
    print("\n=== Check Complete ===")

if __name__ == '__main__':
    main()
