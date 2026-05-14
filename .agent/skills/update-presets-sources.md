# Skill: Update Spooky2 Preset Sources in Remote Database

Apply this skill when new Spooky2 preset files have been acquired (downloaded or extracted) and need to be fully processed and published to the remote database and search frontend.

This is a **multi-step procedural** guide covering extraction, import, verification, and deployment.

---

## Prerequisites

### Environment Variables

Set these in your shell or `.envrc`:

```bash
# Required: Neon PostgreSQL connection string
export NEON_CONN_STRING="postgres://user:pass@host-name.neon.tech/spooky2?sslmode=require"

# Optional: Custom data directory (default: data/presets)
export DATA_DIR="data/presets"

# Optional: Reimport token for remote API endpoint (for deployment)
export REIMPORT_TOKEN="your-secret-token-here"
```

### Dependencies

```bash
# Python packages
pip install -r requirements.txt        # Root requirements
pip install -r scripts/requirements.txt # Script-specific (if needed)

# Node.js dependencies (for frontend rebuild)
cd spooky2-search && npm install

# Wine (for extracting Windows installers, if needed)
sudo apt install wine winetricks
```

---

## Update Pipeline Overview

The complete update process consists of 6 stages:

1. **Acquire** — Download or obtain new Spooky2 installer/database files
2. **Extract** — Parse `.txt` preset files into structured JSON
3. **Import** — Load JSON into Neon PostgreSQL database
4. **Deploy** — Copy JSON to frontend and rebuild static site
5. **Verify** — Confirm data integrity and search functionality
6. **Remote Sync** — Trigger remote server reimport (if applicable)

---

## Stage 1: Acquire Preset Sources

### Option A: Download Official Spooky2 Databases

Run the download script to fetch the latest installers from spooky2.com:

```bash
./scripts/download_databases.sh
```

This downloads to `downloads/`:
- `Spooky2_Presets_*.exe` — Preset Collections
- `Main_Database_*.exe` — Main database
- `DNA_Database_*.exe` — DNA frequencies
- `MW_Database_*.exe` — Molecular weight database

Files are cached; re-run to skip existing downloads.

### Option B: Extract from Existing Wine Installation

If you already have Spooky2 installed under Wine:

```bash
# The preset source is typically at:
ls ~/.wine-spooky2/drive_c/Spooky2/Preset\ Collections/
# Or check:
ls downloads/wine_spooky/drive_c/Spooky2/Preset\ Collections/
```

### Option C: Process Telegram Archive Presets

For presets downloaded from Telegram groups:

```bash
# Place archive files in downloads/telegram_presets/ (or custom location)
python3 scripts/extract_and_postprocess.py \
  --source ./downloads/telegram_presets \
  --output data/presets/telegram_raw
```

This extracts nested archives and organizes by source tag (Proven/Unproven).

---

## Stage 2: Extract Presets to JSON

The main extractor handles both legacy (`List2`/`List4`) and modern (`[Preset]`) formats.

### Basic Extraction

```bash
# Extract from a preset source directory:
python3 scripts/extract_presets.py \
  "/path/to/Preset Collections" \
  --output data/presets
```

Output files in `data/presets/`:
- `presets_all.json` — All programs (main output, ~10–60 MB)
- `extraction_stats.json` — Counts by collection/mode/category
- `file_hashes.txt` — MD5 hashes for incremental updates

### Extraction Arguments

```
--output DIR        Output directory (default: data/presets)
--skip-fingerprint  Skip fingerprint generation (faster)
--verbose           Print detailed progress
```

### Post-Extraction: Assign Categories

If `category` fields are empty (common with new sources), run the categorizer skill:

```bash
# Using the categorize-presets skill, manually or via agent:
# Read .kilo/skills/categorize-presets.md for the keyword-based rules
# Apply to all programs where category is null in presets_all.json
```

Note: The existing `extract_presets.py` already attempts some category inference from folder names, but manual review may be needed.

---

## Stage 3: Import to Neon Database

### Full Reimport (Recommended for Updates)

Clears all existing data and re-imports from scratch:

```bash
python3 import_to_neon.py --clear --verify
```

Flags:
- `--clear` — DELETE all rows before import (use for full updates)
- `--skip-setup` — Skip table/index creation (already exists)
- `--verify` — Print summary statistics after import

**Important**: `--clear` is recommended when source data changes significantly (new collections, deleted programs). Without it, the script uses UPSERT (on conflict update), which is safe for incremental updates but may leave stale rows if programs are removed from source.

### Selective/Incremental Update

For small updates where you only changed a few files:

```bash
python3 import_to_neon.py --verify
```

(Uses `ON CONFLICT DO UPDATE` to merge changes by UUID.)

---

## Stage 4: Deploy to Frontend

### Copy JSON to Frontend

```bash
# Ensure the frontend data directory exists:
mkdir -p spooky2-search/public/data

# Copy the updated presets file:
cp data/presets/presets_all.json spooky2-search/public/data/
```

### Rebuild Frontend Static Assets

```bash
cd spooky2-search
npm run build
```

This generates optimized static files in `dist/`. The production build includes:
- Bundled JavaScript (code-split, tree-shaken)
- CSS styles
- `presets_all.json` copied as-is (not bundled, loaded at runtime)

### Preview Locally (Optional)

```bash
cd spooky2-search
npm run preview
# Opens at http://localhost:4173
```

Verify search works and data loads correctly.

---

## Stage 5: Verify the Update

### Database Verification

```bash
# Connect to Neon and run queries:
psql "$NEON_CONN_STRING" -c "
  SELECT 
    COUNT(*) as total_programs,
    COUNT(*) FILTER (WHERE category IS NOT NULL) as categorized,
    COUNT(DISTINCT collection) as collections,
    COUNT(DISTINCT mode) as modes
  FROM programs;
"

# Sample by collection:
psql "$NEON_CONN_STRING" -c "
  SELECT collection, COUNT(*) as cnt
  FROM programs
  GROUP BY collection
  ORDER BY cnt DESC
  LIMIT 20;
"

# Check for uncategorized programs:
psql "$NEON_CONN_STRING" -c "
  SELECT COUNT(*) as uncategorized
  FROM programs
  WHERE category IS NULL OR category = '';
"
```

### Frontend Verification

1. Run `npm run preview` in `spooky2-search/`
2. Open browser, check console for errors
3. Test a few searches (e.g., "detox", "cancer")
4. Verify result count matches database count
5. Open program detail view, confirm frequencies display

### JSON Validation

```bash
# Validate JSON structure:
python3 -c "import json; json.load(open('data/presets/presets_all.json'))" || exit 1
echo "JSON is valid"

# Check file size:
du -h data/presets/presets_all.json
# Typical: 15–100 MB uncompressed
```

---

## Stage 6: Remote Sync (Production Deployment)

If updating the live site (e.g., GitHub Pages, Vercel, Render), you have two paths:

### Option A: Git Push (Static Hosting)

For static hosting (GitHub Pages, Netlify, Vercel):

```bash
# Commit the updated JSON and rebuilt frontend:
git add data/presets/presets_all.json
git add spooky2-search/dist/
git commit -m "Update presets: YYYY-MM-DD source version"
git push origin main

# Trigger redeploy (platform-specific):
# - GitHub Pages: automatic on push to main
# - Vercel/Netlify: automatic or manual trigger in dashboard
```

Note: The JSON file may be large (>50 MB). Consider:
- Using Git LFS if needed
- Splitting data by collection (future enhancement)
- Checking platform asset size limits (Vercel: 100 MB total)

### Option B: Remote API Reimport (Neon-only update)

If only the database needs updating (frontend already has latest JSON), use the admin API:

```bash
# Trigger remote reimport (requires REIMPORT_TOKEN on server):
curl -X POST "https://your-api-server.com/reimport?token=YOUR_TOKEN"

# With fresh JSON download from URL:
curl -X POST "https://your-api-server.com/reimport?token=YOUR_TOKEN&url=https://example.com/presets_all.json"
```

The server will:
1. Optionally download `presets_all.json` from the URL
2. Run `import_to_neon.py --clear --skip-setup`
3. Return status: `{"status": "ok"}` or error details

**Note**: The remote server's `DATA_DIR` determines where the JSON is stored. The frontend must already load from that location.

---

## Incremental Update Workflow (Automated)

For routine updates, use `check_update.py` which automates Stages 1–4:

```bash
./scripts/check_update.sh
# Or directly:
python3 scripts/check_update.py
```

This script:
1. Finds the current preset source directory
2. Calculates MD5 hashes of all `.txt` files
3. Compares against cached `data/presets/file_hashes.txt`
4. If changes detected, prompts: "Re-extract presets? (y/N)"
5. On confirmation:
   - Runs `extract_presets.py`
   - Updates hash cache
   - Copies JSON to frontend
   - Rebuilds frontend (`npm run build`)

Use this for quick iterations when you've added/changed a few preset files.

---

## Troubleshooting

### Extraction fails: "No preset source found"

```bash
# Ensure Spooky2 is installed under Wine or files are in expected location:
ls ~/.wine-spooky2/drive_c/Spooky2/Preset\ Collections/
# Or:
ls downloads/wine_spooky/drive_c/Spooky2/Preset\ Collections/
```

If missing, run installer through Wine:
```bash
wine downloads/Spooky2_Presets_*.exe /VERYSILENT /DIR="C:\\Spooky2"
```

### Wine installation issues

```bash
# Set up clean Wine prefix (32-bit):
export WINEPREFIX="$HOME/.wine-spooky2"
export WINEARCH=win32
wineboot -u
winetricks -q vcrun6 vcrun2015 riched20 comctl32
```

See `scripts/extract_with_wine.sh` for full procedure.

### Import fails: "NEON_CONN_STRING not set"

```bash
# Set the environment variable:
export NEON_CONN_STRING="postgres://..."
# Or put it in .envrc and reload:
echo 'export NEON_CONN_STRING="..."' >> .envrc
direnv allow .
```

### Frontend build fails: "out of memory"

```bash
# Increase Node memory:
cd spooky2-search
NODE_OPTIONS="--max-old-space-size=4096" npm run build
```

### JSON too large for platform (exceeds 100 MB)

```bash
# Check size:
du -h spooky2-search/public/data/presets_all.json

# If >100 MB compressed, consider:
# 1. Splitting data by collection (future work)
# 2. Using a CDN to host the JSON separately
# 3. Enabling gzip/brotli compression on static host
```

### Database import extremely slow

```bash
# Ensure indexes exist (import_to_neon.py creates them automatically on first run)
# For subsequent runs, use --skip-setup to skip index creation.
# Check pg_stat_progress_create_index in Neon console if stuck.
```

---

## Full Clean Update Procedure (From Scratch)

When you want a completely fresh rebuild from newly downloaded installers:

```bash
# 1. Clean previous extraction artifacts:
rm -rf data/presets/
mkdir -p data/presets

# 2. Download fresh installers (optional, skip if you have them):
./scripts/download_databases.sh

# 3. Extract from the latest installer:
python3 scripts/extract_presets.py \
  ~/.wine-spooky2/drive_c/Spooky2/Preset\ Collections \
  --output data/presets

# 4. Assign categories (if needed):
#    Follow .kilo/skills/categorize-presets.md

# 5. Import to database (full clear):
python3 import_to_neon.py --clear --verify

# 6. Deploy frontend:
cp data/presets/presets_all.json spooky2-search/public/data/
cd spooky2-search && npm run build

# 7. Verify:
psql "$NEON_CONN_STRING" -c "SELECT COUNT(*), mode FROM programs GROUP BY mode;"
```

---

## Notes

- The `source` field in `programs` table indicates origin: `wine` (Spooky2 installer), `telegram` (community), etc.
- The `tag` field groups Telegram sources into `Proven` / `Unproven`.
- `created_at` is set to `NOW()` on each import, allowing timeline queries.
- All timestamps are UTC (PostgreSQL `TIMESTAMP WITH TIME ZONE`).
- The extraction process generates deterministic UUIDs based on preset content, enabling idempotent re-imports.
- For large updates, consider increasing `BATCH_SIZE` in `import_to_neon.py` for faster bulk inserts.

---

## References

- `AGENTS.md` — Project architecture and data flow
- `scripts/extract_presets.py` — Parser implementation
- `import_to_neon.py` — Database import logic
- `api_server.py` — `/reimport` endpoint (lines 316–359)
- `.kilo/skills/categorize-presets.md` — Category assignment rules
