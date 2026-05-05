#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOWNLOADS_DIR="$PROJECT_ROOT/downloads"
DATA_DIR="$PROJECT_ROOT/data/presets"
WINE_PREFIX="$DOWNLOADS_DIR/wine_spooky"
HASH_FILE="$DATA_DIR/file_hashes.txt"
EXTRACTION_STATS="$DATA_DIR/extraction_stats.json"

echo "=== Spooky2 Data Update Check (Hash-based) ==="
echo ""

# Find preset source directory
PRESET_SOURCE=""
if [ -d "$WINE_PREFIX/drive_c/Spooky2/Preset Collections" ]; then
  PRESET_SOURCE="$WINE_PREFIX/drive_c/Spooky2/Preset Collections"
  echo "Found presets in Wine prefix: $PRESET_SOURCE"
elif [ -d "$PROJECT_ROOT/tmp/spooky2_presets/Preset Collections" ]; then
  PRESET_SOURCE="$PROJECT_ROOT/tmp/spooky2_presets/Preset Collections"
  echo "Found presets in temp directory: $PRESET_SOURCE"
else
  echo "No preset source found."
  echo "Checked:"
  echo "  - $WINE_PREFIX/drive_c/Spooky2/Preset Collections"
  echo "  - $PROJECT_ROOT/tmp/spooky2_presets/Preset Collections"
  exit 1
fi

# Calculate current MD5 hashes of all .txt files in parallel
echo ""
echo "Calculating MD5 hashes of preset files (parallel)..."
CURRENT_HASHES=$(mktemp)
find "$PRESET_SOURCE" -name "*.txt" -type f -print0 | \
  xargs -0 -P $(nproc) -I {} md5sum "{}" | \
  sort > "$CURRENT_HASHES"

# Count files
TOTAL_FILES=$(wc -l < "$CURRENT_HASHES")
echo "Found $TOTAL_FILES preset files."

# Compare with stored hashes
if [ -f "$HASH_FILE" ]; then
  echo ""
  echo "Comparing with stored hashes..."
  
  # Create temp files for comparison
  STORED_HASHES=$(mktemp)
  sort "$HASH_FILE" > "$STORED_HASHES"
  
  # Find new or modified files (in current but not in stored, or hash mismatch)
  NEW_FILES=0
  MODIFIED_FILES=0
  
  while read -r hash filepath; do
    filename=$(basename "$filepath")
    # Check if this file is in stored hashes
    STORED_LINE=$(grep "  $filepath$" "$STORED_HASHES" || echo "")
    
    if [ -z "$STORED_LINE" ]; then
      ((NEW_FILES++))
      echo "  NEW: $filename"
    else
      STORED_HASH=$(echo "$STORED_LINE" | awk '{print $1}')
      if [ "$hash" != "$STORED_HASH" ]; then
        ((MODIFIED_FILES++))
        echo "  MODIFIED: $filename"
      fi
    fi
  done < "$CURRENT_HASHES"
  
  # Also check for deleted files (in stored but not in current)
  DELETED_FILES=0
  while read -r hash filepath; do
    if ! grep -q "  $filepath$" "$CURRENT_HASHES"; then
      ((DELETED_FILES++))
    fi
  done < "$STORED_HASHES"
  
  rm -f "$STORED_HASHES"
  
  echo ""
  echo "Results:"
  echo "  New files: $NEW_FILES"
  echo "  Modified files: $MODIFIED_FILES"
  echo "  Deleted files: $DELETED_FILES"
  
  TOTAL_CHANGES=$((NEW_FILES + MODIFIED_FILES + DELETED_FILES))
  
  if [ $TOTAL_CHANGES -gt 0 ]; then
    echo ""
    read -p "Re-extract presets? (y/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Running extraction..."
      cd "$PROJECT_ROOT"
      python3 scripts/extract_presets.py "$PRESET_SOURCE" --output data/presets
      
      echo ""
      echo "Updating hash file..."
      cp "$CURRENT_HASHES" "$HASH_FILE"
      
      echo ""
      echo "Copying to search app..."
      cp data/presets/presets_all.json spooky2-search/public/data/presets_all.json
      
      echo "Rebuilding search app..."
      cd spooky2-search && npm run build
      
      echo ""
      echo "Done! Data updated."
    else
      echo "Skipped re-extraction."
    fi
  else
    echo "No changes detected. Data is up-to-date."
  fi
else
  echo ""
  echo "No stored hashes found. This appears to be the first run."
  echo "Storing current hashes..."
  cp "$CURRENT_HASHES" "$HASH_FILE"
  
  echo "Hash file created at: $HASH_FILE"
  echo ""
  echo "Run the script again after making changes to detect updates."
fi

rm -f "$CURRENT_HASHES"

echo ""
echo "=== Check Complete ==="
