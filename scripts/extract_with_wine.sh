#!/bin/bash
set -e

export WINEPREFIX="$HOME/.wine-spooky2"
export WINEARCH=win32

echo "=== Step 1: Install Windows runtime dependencies ==="
winetricks -q vcrun6 vcrun2015 riched20 comctl32 2>&1 | tail -10 || true

echo "=== Step 2: Ensure wineprefix exists ==="
if [ ! -d "$WINEPREFIX" ]; then
    wineboot -u
    sleep 5
fi

# Create target directory ahead of time (if installer respects /D)
mkdir -p "$WINEPREFIX/drive_c/Spooky2"

INSTALLER="/tmp/spooky2_extract/Spooky2_Starter_Pack_20260408/Spooky2_Setup_20260401.exe"

echo "=== Step 3: Run installer with various flags ==="
echo "Trying /NORESTART /SP- /VERYSILENT /DIR..."

# Use winedbg to trace file operations?
wine "$INSTALLER" /NORESTART /SP- /VERYSILENT /DIR="C:\\Spooky2" 2>&1 | tee /tmp/install_full.log &
INSTALL_PID=$!

# Wait max 6 minutes
for i in $(seq 1 360); do
    if ! ps -p $INSTALL_PID > /dev/null; then
        break
    fi
    sleep 1
    if [ $((i % 30)) -eq 0 ]; then
        echo "Still running at ${i}s..."
    fi
done

if ps -p $INSTALL_PID > /dev/null; then
    echo "Timeout, killing..."
    kill -9 $INSTALL_PID 2>/dev/null || true
fi

echo "=== Step 4: Check for installed files ==="
if [ -d "$WINEPREFIX/drive_c/Spooky2/Preset Collections" ]; then
    echo "Found Preset Collections!"
    cp -r "$WINEPREFIX/drive_c/Spooky2/Preset Collections" /tmp/spooky2_presets/
    ls -la /tmp/spooky2_presets/
    exit 0
fi

# Search more broadly
echo "Searching for Preset Collections..."
for dir in $(find "$WINEPREFIX" -maxdepth 8 -type d 2>/dev/null); do
    if ls "$dir"/*.txt > /dev/null 2>&1; then
        echo "Possible preset dir: $dir"
        ls "$dir"/*.txt 2>/dev/null | head -5
    fi
done

echo "Extraction failed. Last log lines:"
tail -40 /tmp/install_full.log
