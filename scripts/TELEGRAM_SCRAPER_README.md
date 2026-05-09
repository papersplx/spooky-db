# Telegram Preset Scraper

Downloads Spooky2 preset `.txt` files from Telegram groups and integrates them into the Spooky2 Frequency Search pipeline.

## Prerequisites

```bash
pip install telethon
```

## Setup

1. **Get Telegram API credentials:**
   - Go to https://my.telegram.org
   - Create an "App" and note your **API ID** and **API hash**

2. **Option A: User Account (recommended for private groups)**
   - Copy `telegram_config.example.env` to `telegram_config.env`
   - Fill in `api_id`, `api_hash`, and `phone`
   - Add your Telegram group usernames to the `groups` list

3. **Option B: Bot Account**
   - Create a bot via @BotFather on Telegram
   - Add the bot to your groups (it needs to be a member to see messages)
   - Set `bot_token` in the config instead of `api_id`/`api_hash`/`phone`

4. **Important:** If using a user account, the first run will ask for your Telegram verification code (sent via the Telegram app, not SMS).

## Usage

### Test connectivity first (recommended):
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env --test
```

### Dry run (see what would be downloaded):
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env --dry-run
```

### Download files:
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env
```

### Download from a specific group:
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env --group "@mypresetgroup"
```

### Limit messages scanned:
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env --max-messages 500
```

### Filter by date (ISO format):
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env --since 2024-01-01
```

### Verbose/debug output:
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env --verbose
```

### Start fresh (ignore saved progress):
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env --no-resume
```

## Resumability

The scraper saves progress automatically every 50 messages to a `progress.json` file in each group's output directory. If the script is interrupted (Ctrl+C, crash, network error), simply run it again and it will:

- Skip all messages already processed (tracked by message ID)
- Skip all files already downloaded (tracked by file reference hash)
- Resume from the last checkpoint using Telegram's `min_id` parameter

The `--no-resume` flag forces a fresh scrape from scratch.

## Post-Download: Integrate into Dataset

After downloading, post-process the files (extract archives, tag proven/unproven, organize by mode):

```bash
# Extract archives and organize into proven/unproven collection hierarchy
python3 scripts/extract_and_postprocess.py

# Dry run to see what would be done
python3 scripts/extract_and_postprocess.py --dry-run

# Specify custom source/output directories
python3 scripts/extract_and_postprocess.py --source ./downloads/telegram_presets --verbose
```

Then merge into the main dataset:

```bash
# Merge new Telegram files into existing presets_all.json
python3 scripts/integrate_telegram.py

# Or do a full re-extract from both Wine prefix and postprocessed Telegram files:
python3 scripts/integrate_telegram.py --reextract

# Dry run to see what would be merged
python3 scripts/integrate_telegram.py --dry-run
```

### Full Pipeline (scrape → post-process → integrate):
```bash
python3 scripts/telegram_scraper.py --config scripts/telegram_config.env
python3 scripts/extract_and_postprocess.py --verbose
python3 scripts/integrate_telegram.py --verbose
```

## Output Structure

After scraping and post-processing:

```
downloads/telegram_presets/
├── scraper_manifest.json
├── Sp2UnofFILES1/
│   ├── manifest.json
│   ├── progress.json
│   └── extracted/
│       ├── Contact/
│       │   └── *.txt
│       ├── Remote/
│       │   └── *.txt
│       └── ...
├── s2_unof_unproven/
│   ├── manifest.json
│   └── extracted/
│       └── ...

data/presets/telegram_raw/
├── telegram_group_timestamps.json   # API-facing timestamps
├── postprocess_manifest.json        # Overall post-process stats
├── Sp2UnofFILES1/                   # Tagged as "Proven"
│   ├── Contact/
│   │   └── *.txt
│   ├── Remote/
│   │   └── *.txt
│   └── postprocess_manifest.json
└── s2_unof_unproven/                # Tagged as "Unproven"
    └── ...
```

## Configuration Reference

See `scripts/telegram_config.example.env` for all configuration options.

## Troubleshooting

- **"Could not resolve group"**: Make sure the bot/user is a member of the group. For private groups, use a user account (not bot).
- **"FloodWaitError"**: Telegram rate-limiting. The script handles this automatically but you can increase `REQUEST_DELAY` in the config.
- **"ChatForbiddenError"**: The account doesn't have access to the group.
- **No files downloaded**: Check that files are being shared as `.txt` attachments in the group, not as text messages.