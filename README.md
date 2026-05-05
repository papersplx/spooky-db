# Spooky2 Frequency Search

A React + Vite SPA that provides full-text search over Spooky2 frequency presets.

**Live site**: https://papersplx.github.io/spooky-db/

## Project Summary

A React + Vite SPA that provides full-text search over Spooky2 frequency presets. Data is extracted from the Spooky2 installer's `Preset Collections/` directory and served as static JSON.

## Tech Stack

- **Frontend**: React 19, Vite
- **Search**: Fuse.js (client-side fuzzy search)
- **Styling**: Plain CSS (CSS variables for theming)
- **Hosting**: Static files (Vercel/Render/Netlify)

## Data Flow

1. **Extraction** (`scripts/extract_presets.py`) parses `.txt` preset files from Spooky2 installer into JSON
   - Supports two formats:
     - **Legacy**: `List2="description"` and `List4="freqs"` (key=value, multiline)
     - **Modern**: `[Preset]` sections with quoted `Key=Value` lines (`PresetName=`, `Loaded_Frequencies=`)
   - Handles Bacon-encoded frequencies (starting with `~`) as opaque tokens
2. **JSON files** placed in `public/data/` (ignored by git due to size)
3. **App loads** `presets_all.json` at startup via `src/data/loader`
4. **Search** uses Fuse.js to match against name/description fields
5. **Results** displayed in `ResultsList`, detail in `ProgramDetail`

## Data Schema

Program object:

```typescript
interface Program {
  id: string;           // UUID
  name: string;         // Program name (from filename or PresetName field)
  description: string;  // List2 value or Preset_Notes
  code: string;         // Raw frequency code (List4 or Loaded_Frequencies)
  entry_type: 'program' | 'preset' | 'reference';  // program has frequencies; preset/container has Loaded_Programs chain
  loaded_programs?: string;  // (for presets) comma-separated program names this preset chains together
  frequencies: Array<{
    type: 'frequency' | 'sweep' | 'bacon' | 'raw';
    freq?: number;
    endFreq?: number;
    dwell?: number;
    waveform?: number;
    amplitude?: number;
    offset?: number;
    gate?: number;
    factor?: number;
    constant?: number;
    molecular?: number;
    basePairs?: number;
    raw?: string;       // For Bacon/unknown tokens
  }>;
  preset_file: string;
  collection: string;   // e.g., "Factory/Detox/Contact"
  mode: 'Contact' | 'Remote' | 'Plasma' | 'Coil' | 'Scalar' | 'Laser' | 'Other';
  category?: string;    // e.g., "Detox"
  default_dwell?: number;
}
```

## Frequency Code Syntax

Spooky2 codes are comma-separated tokens:

- `100` - 100 Hz
- `100-200` - Sweep from 100 to 200 Hz
- `100-200=1800` - Sweep with 1800s dwell per step
- `300=600` - 300 Hz for 600 seconds
- `W0` - Sine waveform
- `W1` - Square waveform
- `W2` - Triangle waveform
- `A05` - 5V amplitude
- `O50` - 50% offset
- `o20` - -20% offset
- `G1` - Gate ON
- `F2` - Factor 2
- `C3` - Constant 3
- `M4` - Molecular weight 4
- `B5` - Base pairs 5
- `~XXXXX` - Bacon-encoded frequency (opaque token, copy as-is)

Modifiers can be combined: `100=600 W1 A09 O50 G1`

## Code Conventions

- **Imports**: Absolute imports from `src/`
- **Components**: Functional, hooks for state
- **CSS**: Component-scoped CSS files
- **No comments** in code (as per project policy) - use documentation files
- **Error handling**: Graceful degradation if data fails to load

## Adding New Features

1. **New frequency token type**: Update `parseFrequencyCode` in both Python and JS
2. **New filter**: Add to `FilterPanel`, state in `App.jsx`, apply filter in `performSearch`
3. **Change data schema**: Update both extractor and parser, regenerate data

## Performance Considerations

- Data size: 5-15 MB gzipped
- 50k items in memory - handled by Fuse.js efficiently
- Debounced search (300ms) to avoid excessive re-indexing
- Results limited to 5000 displayed; full count shown in stats
- CSS containment and React.memo as needed

## Common Tasks

**Add a new collection**:
- Place preset files in `Preset Collections/<collection>/` subfolder
- Re-run extraction: `python3 scripts/extract_presets.py <path> --output data/presets`
- Copy output to `spooky2-search/public/data/`
- Redeploy

**Update waveform mapping**:
- Edit `WAVEFORM_NAMES` in both `frequencyParser.js` and `extract_presets.py`
- Reference: Spooky2 `Waveforms.h` (from s2 project)

**Change search behavior**:
- Edit `spooky2-search/src/search/fuseConfig.js`
- Tweak `threshold`, `keys`, `weight` as needed

## Estimating Data Size

- Expected 10,000–60,000 programs depending on which Spooky2 databases are included
- JSON size: ~5–50 MB compressed; ~15–100 MB uncompressed
- Vercel limit: 100 MB static assets (compressed counts toward limit)
- If exceeding limit, split by collection and lazy-load

## Testing

No test suite currently (by design). Validate by:
1. Run extraction on sample presets
2. Verify search returns expected results
3. Test UI in dev server
4. Check production build size: `npm run build && npm run preview`

## Troubleshooting

**Data not loading**: Check `public/data/presets_all.json` exists and is valid JSON.

**No search results**: Verify Fuse index includes correct keys; open DevTools and inspect `fuse` object.

**Large bundle**: Vite should tree-shake; data file is separate static asset.

**Slow search**: Ensure not running on low-end device; 50k items should query <100ms.

## Deployment Notes

- **Vercel**: 100 MB limit. Our JSON is ~10-20 MB depending on dataset.
- **Render**: No hard limit mentioned; good fallback.
- **Data updates**: Rerun extraction, commit/push new JSON, trigger redeploy.
- **CDN**: Both platforms provide global CDN automatically.

## Reference Links

- Spooky2 downloads: https://cancerclinic.co.nz/downloads.html
- s2 (open-source CLI): https://github.com/calum74/s2
- Fuse.js docs: https://fusejs.io
- Spooky2 Frequency List: https://www.spooky2-mall.com/download/spooky2rifefrequencylist.pdf

## Current Status

### What's Working
- Extracted 25,947 programs from Spooky2 Presets installer (20260422)
- Full-text search with Fuse.js (supports mode/type keywords)
- Program detail view with frequency token parsing
- Clickable program chains in presets (shows description and frequencies if available)
- Synonym search (mold ↔ fungus)
- Progress tracking during data load
- Production build: 72.55 KB gzipped JS

### Known Limitations
- **Main Database (.s2d) is encrypted**: The Spooky2 Main Database uses a proprietary encrypted format (ZIP) that can only be read by Spooky2 software. Programs referenced in `loaded_programs` that belong to the Main Database will show "Program details not in database. Add Main Database to enable."
- **Custom databases**: Only the preset programs (25,947) are currently extracted. The Main Database contains 60,000+ programs but cannot be extracted without running Spooky2 software on Windows.
- **Wine compatibility**: Attempts to run Spooky2 in Wine for database export have been unsuccessful in this environment. The installer fails with "Application could not be started" even with winetricks corefonts and vcrun6.

### To Enable Full Database
1. Install Spooky2 on a Windows machine (download from https://cancerclinic.co.nz/downloads.html)
2. Open Spooky2 software
3. Use File → Export Database to save as CSV
4. Convert CSV to our JSON format using `scripts/convert_csv.py` (to be created)
5. Add the exported programs to `data/presets/presets_all.json`

### Quick Test
```bash
cd spooky2-search
npm run dev
# Open http://localhost:5173
# Search "mold" → should return 83 Fungus and Mold programs
# Click any result → see details
# For presets: click chain items → expand to see program info
```

### File Structure
```
spooky-db/
├── scripts/
│   ├── extract_presets.py      # Extract presets from .txt files
│   ├── download_databases.sh  # Download latest Spooky2 files
│   └── convert_csv.py          # (TODO) Convert CSV to JSON
├── spooky2-search/
│   ├── public/data/
│   │   ├── presets_all.json   # Main data file (76 MB)
│   │   └── by_collection/      # (optional) Per-collection files
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchBox.jsx
│   │   │   ├── FilterPanel.jsx
│   │   │   ├── ResultsList.jsx
│   │   │   ├── ProgramDetail.jsx  # Shows chain items with clickable programs
│   │   │   └── StatsBar.jsx
│   │   ├── data/loader.js
│   │   ├── search/fuseConfig.js
│   │   ├── utils/frequencyParser.js
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── index.css
│   └── package.json
├── downloads/                  # Downloaded .exe installers
│   ├── wine_spooky/              # Wine prefix for Spooky2 (installation attempts)
│   ├── Spooky2_Presets_20260422.exe
│   ├── Main_Database_20260503.exe
│   ├── DNA_Database_20251223.exe
│   ├── MW_Database_20260228.exe
│   └── Starter_Pack_20260408/
├── data/presets/              # Extraction output
│   ├── presets_all.json
│   └── extraction_stats.json
└── README.md
```
spooky-db/
├── scripts/
│   ├── extract_presets.py      # Extract presets from .txt files
│   ├── download_databases.sh  # Download latest Spooky2 files
│   └── convert_csv.py          # (TODO) Convert CSV to JSON
├── spooky2-search/
│   ├── public/data/
│   │   ├── presets_all.json   # Main data file (76 MB)
│   │   └── by_collection/      # (optional) Per-collection files
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchBox.jsx
│   │   │   ├── FilterPanel.jsx
│   │   │   ├── ResultsList.jsx
│   │   │   ├── ProgramDetail.jsx  # Shows chain items with clickable programs
│   │   │   └── StatsBar.jsx
│   │   ├── data/loader.js
│   │   ├── search/fuseConfig.js
│   │   ├── utils/frequencyParser.js
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── index.css
│   └── package.json
├── downloads/                  # Downloaded .exe installers
├── data/presets/              # Extraction output
│   ├── presets_all.json
│   └── extraction_stats.json
└── README.md
```

## Recent Changes
- Fixed: ResultsList now shows program text (fixed Fuse.js result format handling)
- Fixed: Removed duplicate mode badges in ProgramDetail
- Fixed: Removed custom fonts (now uses system-ui only)
- Fixed: Loading spinner with progress percentage
- Added: Clickable program chains in ProgramDetail
- Added: "Program details not in database" message for Main Database programs
- Downloaded: Spooky2 Presets, Main Database, DNA Database, MW Database
- Extracted: 25,947 programs from preset files
- Known issue: Main Database (.s2d) is encrypted and cannot be extracted without Spooky2 software
