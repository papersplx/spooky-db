# Skill: Update Spooky2 Preset Sources in Remote Database

Apply this skill when new Spooky2 preset files have been acquired (downloaded or extracted) and need to be fully processed and published to the remote database and search frontend.

This guide incorporates fixes for common pitfalls (e.g., missing txt file copying, dependency issues) and provides a streamlined workflow.

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
# System packages (Debian/Ubuntu)
sudo apt update
sudo apt install -y python3-pip python3-venv wine winetricks unzip p7zip-full

# Python virtual environment (if not already present)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r scripts/requirements.txt

# Node.js (for frontend)
# Install via nvm or your package manager; ensure npm >= 9
cd spooky2-search && npm ci
```

---

## Streamlined Update Pipeline

The following steps combine extraction, import, and deployment while avoiding the errors encountered earlier.

### 1. Acquire Preset Sources

#### Option A: Download Official Spooky2 Databases
```bash
./scripts/download_databases.sh
```
Downloads to `downloads/`:
- `Spooky2_Presets_*.exe` (Preset Collections)
- `Main_Database_*.exe` (Main database)
- `DNA_Database_*.exe` (DNA frequencies)
- `MW_Database_*.exe` (Molecular weight)

#### Option B: Process Telegram Archive Presets
Place archives (or already‑extracted `.txt` files) in `downloads/telegram_presets/`.  
The extractor will handle nested archives and organize by source tag.

### 2. Extract and Post‑Process (Fixed Script)

Run the corrected post‑processor that **always copies `.txt` files**, even when no archives are present:

```bash
python3 scripts/extract_and_postprocess.py \
    --source ./downloads/telegram_presets \
    --output data/presets/telegram_raw
```

**What changed**: The earlier version returned early when no archives were found, skipping the copy step. The fixed version processes:
-initial `.txt` files into a temporary work directory.
2. Extract any archives (if present).
3. Copy the final `.txt` set to the extraction folder.
4. Organize into `Proven/Contact/`, `Proven/Remote/`, etc.

After this step you will see:
```
data/presets/telegram_raw/Spooky2_PROVEN_FILES/Proven/Remote/<preset>.txt
data/presets/telegram_raw/Spooky2_UNPROVEN/.../...
```

### 3. Extract Presets from All Sources (Wine + Telegram)

```bash
# Extract from Wine prefix (if you have Spooky2 installed via wine)
python3 scripts/extract_presets.py \
    "$HOME/.wine-spooky2/drive_c/Spooky2/Preset Collections" \
    --output data/presets \
    --skip-fingerprint   # faster if you don't need hashes

# The above creates/updates data/presets/presets_all.json with wine source.
# Then merge Telegram presets:
python3 scripts/integrate_telegram.py
```

`integrate_telegram.py`:
- Deduplicates against existing `presets_all.json`
- Tags incoming records with `source: telegram` and `tag: Proven`/`Unproven`
- Writes a new `presets_all.json` (and a backup)

### 4. Import into Neon Database

```bash
# Full refresh (recommended when source set changes)
python3 import_to_neon.py --clear --verify

# For incremental updates (safe if no records were removed):
python3 import_to_neon.py --verify
```

The script uses `ON CONFLICT (id) DO UPDATE` to upsert by UUID, ensuring idempotency.

### 5. Deploy to Frontend

```bash
# Ensure the frontend data directory exists
mkdir -p spooky2-search/public/data

# Copy the updated preset file
cp data/presets/presets_all.json spooky2-search/public/data/

# Rebuild the SPA
cd spooky2-search
npm run build   # produces optimized static files in dist/
```

### 6. Verify

#### Database
```bash
psql "$NEON_CONN_STRING" -c "
  SELECT COUNT(*) AS total,
         COUNT(*) FILTER (WHERE tag = 'Proven') AS proven,
         COUNT(*) FILTER (WHERE tag = 'Unproven') AS unproven
  FROM programs;
"
```

#### Frontend
```bash
cd spooky2-search
npm run preview   # http://localhost:4173
```
Check console for errors, try a few searches, and confirm result counts match the DB.

#### JSON Validity
```bash
python3 -c "import json; json.load(open('data/presets/presets_all.json'))" && echo "JSON OK"
```

---

## Automation Helper Script

For routine updates, you can use the provided helper (or create your own):

```bash
# scripts/update_all.sh  (example)
#!/usr/bin/env bash
set -euo pipefail

echo "=== Acquiring latest sources ==="
./scripts/download_databases.sh   # optional, skip if you already have files

echo "=== Processing Telegram presets ==="
python3 scripts/extract_and_postprocess.py --source ./downloads/telegram_presets

echo "=== Extracting from Wine prefix ==="
python3 scripts/extract_presets.py "$HOME/.wine-spooky2/drive_c/Spooky2/Preset Collections" --output data/presets --skip-fingerprint

echo "=== Merging Telegram data ==="
python3 scripts/integrate_telegram.py

echo "=== Importing to Neon (full refresh) ==="
python3 import_to_neon.py --clear --verify

echo "=== Deploying to frontend ==="
mkdir -p spooky2-search/public/data
cp data/presets/presets_all.json spooky2-search/public/data/
cd spooky2-search && npm run build

echo "✅ Update complete."
```

Make it executable (`chmod +x scripts/update_all.sh`) and run it whenever you have new source material.

---

## Troubleshooting Quick Reference

| Symptom | Fix |
|---------|-----|
| `extract_and_postprocess.py` reports "0 files" after run | Ensure you are using the **fixed** version (the one that copies `.txt` files when no archives exist). The skill now references the corrected script. |
| `ModuleNotFoundError: psycopg` | Install inside the venv: `.venv/bin/pip install psycopg-binary` (or `psycopg` from requirements). |
| Wine installer fails | Use a clean 32‑bit prefix: `export WINEPREFIX="$HOME/.wine-spooky2"; export WINEARCH=win32; wineboot -u; winetricks vcrun6 vcrun2015`. |
| Frontend bundle too large (>100 MB) | Enable gzip/brotli on your static host, or consider splitting `presets_all.json` by chunk (future work). |
| Duplicate entries after import | The import uses `ON CONFLICT DO UPDATE` on `uuid`; duplicates should not appear. If they do, re‑run with `--clear` to start fresh. |
| JSON syntax error | Validate with `python3 -m json.tool data/presets/presets_all.json > /dev/null`. |

---

## Notes

- The `source` column in `programs` distinguishes `wine` (official installer) from `telegram` (community).
- The `tag` column marks Telegram provenance as `Proven` or `Unproven`.
- All timestamps are stored as UTC `TIMESTAMP WITH TIME ZONE`.
- UUIDs are deterministic based on preset content, enabling safe re‑imports.

---

## References

- `AGENTS.md` – overall architecture and data flow
- `scripts/extract_and_postprocess.py` – fixed post‑processor
- `scripts/extract_presets.py` – legacy/modern parser
- `scripts/integrate_telegram.py` – deduplication & tagging
- `import_to_neon.py` – Neon import with UPSERT
- `api_server.py` – `/reimport` endpoint for remote triggers
- `.kilo/skills/categorize-presets.md` – keyword‑based category assignment

