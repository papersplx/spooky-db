#!/bin/bash
set -e

BASE_URL="https://cancerclinic.co.nz"
DOWNLOAD_PAGE="$BASE_URL/downloads.html"
DOWNLOAD_DIR="$(dirname "$0")/../downloads"
mkdir -p "$DOWNLOAD_DIR"

echo "Fetching download page..."
HTML=$(curl -s -L "$DOWNLOAD_PAGE")

get_file_url() {
  local title="$1"
  local prefix=$(echo "$title" | tr ' ' '_')
  echo "$HTML" | grep -oP "href=\"\KewExternalFiles/${prefix}_[0-9]+\.exe" | head -1
}

FILES=(
  "Spooky2 Presets"
  "Main Database"
  "DNA Database"
  "MW Database"
)

for title in "${FILES[@]}"; do
  link=$(get_file_url "$title")
  if [ -z "$link" ]; then
    echo "WARN: Could not find download link for $title"
    continue
  fi
  filename=$(basename "$link")
  dest="$DOWNLOAD_DIR/$filename"
  if [ -f "$dest" ]; then
    echo "SKIP: $filename (already exists)"
  else
    echo "DOWNLOAD: $filename"
    curl -L -o "$dest" "$BASE_URL/$link"
  fi
done

echo ""
echo "Downloaded files:"
ls -lh "$DOWNLOAD_DIR"/*.exe 2>/dev/null || echo "No .exe files found"
