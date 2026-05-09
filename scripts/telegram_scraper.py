#!/usr/bin/env python3
"""
Telegram Group Scraper for Spooky2 Preset Files
================================================

Connects to Telegram groups/channels and downloads all .txt preset files
shared in them, organizing them into a directory structure compatible
with the Spooky2 extraction pipeline (extract_presets.py).

Supports resumable scraping: progress is saved incrementally to
per-group progress.json files. On restart, scraping resumes from
the last processed message.

Usage:
    1. Copy telegram_config.example.env to telegram_config.env and fill in credentials
    2. python3 telegram_scraper.py --config telegram_config.env

Authentication:
    - User account (phone + code): Best for private groups you're already a member of
    - Bot token: Bot must already be added to the groups as a member

Requirements:
    pip install telethon
    # For user auth: you'll need your phone number and Telegram code
    # For bot auth: get a bot token from @BotFather
"""

import os
import sys
import re
import json
import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Set

from telethon import TelegramClient, errors
from telethon.tl.types import MessageMediaDocument


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    # Authentication - provide one of these
    "api_id": "",                    # Telegram API ID (get from https://my.telegram.org)
    "api_hash": "",                  # Telegram API hash
    "phone": "",                     # Phone number for user auth (with country code, e.g. +1234567890)
    # OR
    "bot_token": "",                 # Bot token for bot auth (mutually exclusive with phone)

# Target groups
    "groups": [],                    # List of group usernames (e.g. ["@spooky2group"])
                                      # Can be usernames, invite links, or numeric IDs

    # Date filtering
    "since": None,                   # ISO format date string to start from (e.g. "2024-01-01")

    # Output
    "output_dir": "telegram_presets",  # Base directory for downloaded files
    "max_messages": 0,               # Max messages to scan per group (0 = unlimited)
    "file_types": [".txt"],          # File extensions to download

    # Resumability
    "resume": True,                  # Resume from last saved progress on restart
    "save_interval": 50,             # Save progress every N messages

    # Rate limiting & retries
    "request_delay": 0.5,           # Delay between batch requests (seconds)
    "max_retries": 3,               # Retries for failed downloads
    "retry_delay": 5,               # Delay between retries (seconds)

    # Logging
    "log_level": "INFO",            # DEBUG, INFO, WARNING, ERROR
    "log_file": "telegram_scraper.log",
}


def load_config(config_path: str) -> Dict:
    """Load configuration from an env-style config file."""
    config = dict(DEFAULT_CONFIG)

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")

                    # Handle list values (JSON-like arrays)
                    if value.startswith("[") and value.endswith("]"):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            value = [v.strip().strip('"').strip("'")
                                     for v in value[1:-1].split(",") if v.strip()]

                    # Handle boolean-like values
                    elif value.lower() in ("true", "false"):
                        value = value.lower() == "true"

                    # Handle integer values
                    elif value.isdigit():
                        value = int(value)

                    # Handle float values
                    elif re.match(r'^\d+\.\d+$', value):
                        value = float(value)

                    config[key.strip().lower()] = value

    # Validate required fields
    has_phone = config.get("phone", "") and config.get("api_id", "") and config.get("api_hash", "")
    has_bot = config.get("bot_token", "")

    if not has_phone and not has_bot:
        raise ValueError(
            "Authentication not configured. Provide either:\n"
            "  - phone + api_id + api_hash (user auth), OR\n"
            "  - bot_token (bot auth)"
        )

    if has_phone and has_bot:
        raise ValueError(
            "Both phone and bot_token are set. Use only one authentication method."
        )

    if not config.get("groups"):
        raise ValueError("No groups specified. Add group usernames to the 'groups' list in config.")

    return config


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_level: str, log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging for the scraper."""
    logger = logging.getLogger("telegram_scraper")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# Progress persistence (resumability)
# ---------------------------------------------------------------------------

def load_progress(group_slug: str, output_dir: Path) -> Dict:
    """Load progress state from disk for a group."""
    progress_path = output_dir / group_slug / "progress.json"

    if not progress_path.exists():
        return {"seen_message_ids": [], "downloaded_hashes": {}, "last_message_id": None}

    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Migrate old format (list of IDs) to new format (dict with metadata)
        if isinstance(data.get("seen_message_ids"), list):
            data["seen_message_ids"] = [str(x) for x in data["seen_message_ids"]]
        if "downloaded_hashes" not in data:
            data["downloaded_hashes"] = {}

        return data
    except (json.JSONDecodeError, IOError):
        return {"seen_message_ids": [], "downloaded_hashes": {}, "last_message_id": None}


def save_progress(group_slug: str, output_dir: Path, progress: Dict):
    """Save progress state to disk for a group."""
    progress_path = output_dir / group_slug / "progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


async def create_client(config: Dict) -> TelegramClient:
    """Create and connect a Telegram client."""
    session_name = "telegram_scraper_session"

    if config.get("bot_token"):
        client = TelegramClient(session_name, int(config["api_id"]), config["bot_token"])
        await client.start(bot_token=config["bot_token"])
    else:
        client = TelegramClient(session_name, int(config["api_id"]), config["api_hash"])
        await client.start(phone=config.get("phone"))

    return client


async def resolve_peer(client: TelegramClient, group_identifier: str):
    """Resolve a group identifier (username, invite link, or ID) to a peer."""
    # Strip leading @
    identifier = group_identifier.lstrip("@")

    # Try as username
    if not identifier.isdigit():
        try:
            entity = await client.get_entity(identifier)
            return entity
        except (ValueError, errors.FloodWaitError):
            pass

    # Try as invite link
    if "joinchat" in identifier or "+" in identifier:
        try:
            entity = await client.get_entity(identifier)
            return entity
        except (ValueError, errors.FloodWaitError):
            pass

    # Try as numeric ID
    try:
        peer_id = int(identifier)
        # Try as channel (negative IDs for channels/groups)
        for test_id in [peer_id, -100 - peer_id if peer_id > 0 else peer_id]:
            try:
                entity = await client.get_entity(test_id)
                return entity
            except (ValueError, errors.FloodWaitError):
                continue
    except ValueError:
        pass

    return None


async def get_group_info(client: TelegramClient, peer) -> Dict:
    """Get group/channel info."""
    # Use peer's own title if available (InputPeer objects have title)
    title = getattr(peer, 'title', None)
    if title:
        return {
            "title": title,
            "participants_count": getattr(peer, 'participants_count', 0),
            "username": getattr(peer, 'username', None),
        }

    # Fall back to re-resolving the entity
    try:
        if hasattr(peer, 'channel_id'):
            entity = await client.get_entity(peer.channel_id)
            full = getattr(entity, 'chat', entity)
            return {
                "title": getattr(full, 'title', type(peer).__name__),
                "participants_count": getattr(full, 'participants_count', 0),
                "username": getattr(full, 'username', None),
            }
    except Exception:
        pass

    return {"title": type(peer).__name__, "participants_count": 0, "username": None}


# ---------------------------------------------------------------------------
# File downloading
# ---------------------------------------------------------------------------

def make_safe_filename(name: str, extension: str) -> str:
    """Sanitize a filename to be filesystem-safe."""
    # Remove or replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')

    # Truncate to a reasonable length (200 chars) to avoid OS limits
    # while preserving space for the extension
    max_base = 200 - len(extension) - 1
    if len(name) > max_base:
        name = name[:max_base]

    # Ensure it has the right extension
    if not name.lower().endswith(extension.lower()):
        name = f"{name}.{extension.lstrip('.').lower()}"

    return name


def get_unique_path(output_dir: Path, filepath: Path) -> Path:
    """Get a unique file path, appending numbers for duplicates."""
    dest = output_dir / filepath.name

    if not dest.exists():
        return dest

    stem = filepath.stem
    suffix = filepath.suffix
    counter = 1

    while dest.exists():
        dest = output_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    return dest


async def download_file(
    client: TelegramClient,
    message,
    output_dir: Path,
    sub_dir: str,
    file_types: List[str],
    max_retries: int,
    retry_delay: float,
    logger: logging.Logger,
    seen_hashes: Dict[str, str],
) -> Optional[Dict]:
    """Download a file from a Telegram message if it matches our criteria."""
    media = message.media

    # Only process actual document messages, not photos or other media
    if not isinstance(media, MessageMediaDocument):
        return None

    doc = media.document
    if not doc:
        return None

    # Find a matching file attribute
    filename = None
    file_ext = None

    for attr in doc.attributes:
        if hasattr(attr, 'file_name'):
            filename = attr.file_name
            file_ext = os.path.splitext(filename)[1].lower()
            break

    if not filename:
        filename = str(doc.id)
        file_ext = ".bin"

    if file_ext.lower() not in [ft.lower() for ft in file_types]:
        return None

    # Create subdirectory path
    sub_path = output_dir / sub_dir if sub_dir else output_dir
    sub_path.mkdir(parents=True, exist_ok=True)

    # Check for duplicates by file reference
    file_ref = doc.id
    if file_ref in seen_hashes:
        logger.debug(f"Skipping duplicate: {filename} (already seen as {seen_hashes[file_ref]})")
        return None

    # Sanitize filename
    safe_name = make_safe_filename(
        re.sub(r'\.(txt|TXT)$', '', filename),
        ".txt"
    )

    dest_path = get_unique_path(sub_path, Path(safe_name))

    # Download with retries
    for attempt in range(max_retries):
        try:
            await client.download_media(
                message,
                file=str(dest_path),
            )
            seen_hashes[file_ref] = str(dest_path)
            file_size = dest_path.stat().st_size if dest_path.exists() else 0
            logger.info(f"  Downloaded: {dest_path.name} ({file_size:,} bytes)")
            return {
                "filename": dest_path.name,
                "path": str(dest_path),
                "size": file_size,
                "message_id": message.id,
                "date": message.date.isoformat() if message.date else None,
            }
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"  Flood wait: sleeping {wait_time}s (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.warning(f"  Download failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

    return None


# ---------------------------------------------------------------------------
# Message iteration
# ---------------------------------------------------------------------------

async def scrape_group(
    client: TelegramClient,
    peer,
    output_dir: Path,
    config: Dict,
    logger: logging.Logger,
) -> Dict:
    """Scrape all messages from a Telegram group/channel."""

    group_info = await get_group_info(client, peer)
    group_name = group_info.get("title", str(peer))
    group_slug = re.sub(r'[^a-zA-Z0-9]+', '_', group_name).strip('_')

    # Cap slug length to avoid filesystem issues
    max_slug_len = 100
    if len(group_slug) > max_slug_len:
        group_slug = group_slug[:max_slug_len].rstrip('_')

    sub_dir = group_slug
    group_output_dir = output_dir / sub_dir
    group_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"\n{'='*60}")
    logger.info(f"Scraping: {group_name}")
    logger.info(f"Members: {group_info.get('participants_count', 'N/A')}")
    logger.info(f"Username: @{group_info.get('username', 'N/A')}")
    logger.info(f"Output: {group_output_dir}/")
    logger.info(f"{'='*60}")

    # Load progress for resumability
    progress = load_progress(group_slug, output_dir)
    seen_message_ids: Set[int] = set(int(x) for x in progress.get("seen_message_ids", []))
    seen_hashes: Dict[str, str] = progress.get("downloaded_hashes", {})
    last_message_id = progress.get("last_message_id")

    stats = {
        "group": group_name,
        "total_messages_scanned": 0,
        "files_downloaded": 0,
        "files_failed": 0,
        "files_skipped": 0,
        "downloaded_files": [],
        "date_range": {"earliest": None, "latest": None},
        "error": None,
    }

    file_types = config.get("file_types", [".txt"])
    max_messages = config.get("max_messages", 0)
    save_interval = config.get("save_interval", 50)
    batch_count = 0

    # Skip already-downloaded files from stats
    stats["files_downloaded"] = len(seen_hashes)

    try:
        # Use iter_reverse to get oldest messages first (better for large groups)
        # or iter to get newest first
        offset_date = None
        if config.get("since"):
            since_str = config["since"]
            # Parse ISO format date string
            offset_date = datetime.fromisoformat(since_str.replace("Z", "+00:00"))

        # Skip already-processed messages if resuming
        offset_id = 0
        if config.get("resume") and last_message_id is not None:
            offset_id = last_message_id + 1
            logger.info(f"  Resuming from message ID {offset_id} ({len(seen_message_ids)} msgs already seen, {len(seen_hashes)} files already downloaded)")

        messages_iter = client.iter_messages(
            peer,
            reverse=True,  # Oldest first
            limit=max_messages if max_messages > 0 else None,
            offset_date=offset_date,
            offset_id=offset_id,
        )

        async for message in messages_iter:
            batch_count += 1
            stats["total_messages_scanned"] += 1

            # Skip already-seen messages
            if message.id in seen_message_ids:
                continue

            # Track date range
            if message.date:
                date_str = message.date.isoformat()
                if stats["date_range"]["earliest"] is None:
                    stats["date_range"]["earliest"] = date_str
                stats["date_range"]["latest"] = date_str

            # Progress logging
            if batch_count % 100 == 0:
                logger.info(
                    f"  Progress: {stats['total_messages_scanned']} messages scanned, "
                    f"{stats['files_downloaded']} files downloaded"
                )

            # Try to download file from message
            result = await download_file(
                client=client,
                message=message,
                output_dir=group_output_dir,
                sub_dir="",
                file_types=file_types,
                max_retries=config.get("max_retries", 3),
                retry_delay=config.get("retry_delay", 5),
                logger=logger,
                seen_hashes=seen_hashes,
            )

            if result:
                stats["files_downloaded"] += 1
                stats["downloaded_files"].append(result)
            elif message.media and hasattr(message.media, 'document'):
                doc = message.media.document
                if doc:
                    # Check if it was skipped due to file type
                    is_target_type = False
                    for attr in doc.attributes:
                        if hasattr(attr, 'file_name'):
                            ext = os.path.splitext(attr.file_name)[1].lower()
                            if ext in [ft.lower() for ft in file_types]:
                                is_target_type = True
                                break

                    if is_target_type:
                        stats["files_failed"] += 1
                    else:
                        stats["files_skipped"] += 1

            # Mark message as processed
            seen_message_ids.add(message.id)

            # Periodic progress save
            if batch_count % save_interval == 0:
                progress = {
                    "seen_message_ids": [str(x) for x in seen_message_ids],
                    "downloaded_hashes": seen_hashes,
                    "last_message_id": message.id,
                }
                save_progress(group_slug, output_dir, progress)

            # Rate limiting
            delay = config.get("request_delay", 0.5)
            if delay > 0:
                await asyncio.sleep(delay / 10)  # Small delay per message

    except errors.FloodWaitError as e:
        logger.error(f"Rate limited! Must wait {e.seconds} seconds.")
        stats["error"] = f"FloodWaitError: {e.seconds}s"
    except errors.ChatForbiddenError:
        logger.error(f"Access denied to group: {group_name}")
        stats["error"] = "ChatForbiddenError"
    except errors.ChannelInvalidError:
        logger.error(f"Channel invalid: {group_name}")
        stats["error"] = "ChannelInvalidError"
    except Exception as e:
        logger.error(f"Error scraping group {group_name}: {type(e).__name__}: {e}")
        stats["error"] = f"{type(e).__name__}: {e}"

    # Final progress save (always, even on error)
    progress = {
        "seen_message_ids": [str(x) for x in seen_message_ids],
        "downloaded_hashes": seen_hashes,
        "last_message_id": max(seen_message_ids) if seen_message_ids else None,
    }
    save_progress(group_slug, output_dir, progress)

    # Save group manifest
    manifest_path = group_output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"\nGroup manifest saved: {manifest_path}")

    return stats


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

async def run_scraper(config: Dict, logger: logging.Logger) -> Dict:
    """Main scraper orchestrator."""
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Spooky2 Telegram Preset Scraper")
    logger.info("=" * 60)
    logger.info(f"Output directory: {output_dir.resolve()}")
    logger.info(f"Target groups: {config['groups']}")
    logger.info(f"File types: {config['file_types']}")
    logger.info(f"Max messages per group: {config['max_messages'] or 'Unlimited'}")

    # Create client and connect
    logger.info("\nConnecting to Telegram...")
    client = await create_client(config)
    me = await client.get_me()

    if config.get("bot_token"):
        logger.info(f"Connected as bot: @{me.username}")
    else:
        logger.info(f"Connected as user: {me.first_name} (@{me.username})")

    overall_stats = {
        "total_groups_processed": 0,
        "total_files_downloaded": 0,
        "total_messages_scanned": 0,
        "groups": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    for group_identifier in config["groups"]:
        logger.info(f"\nResolving: {group_identifier}")

        peer = await resolve_peer(client, group_identifier)

        if peer is None:
            logger.error(f"  Could not resolve: {group_identifier}")
            overall_stats["groups"].append({
                "identifier": group_identifier,
                "error": "Could not resolve group identifier",
            })
            continue

        try:
            stats = await scrape_group(client, peer, output_dir, config, logger)
            stats["identifier"] = group_identifier
            overall_stats["groups"].append(stats)
            overall_stats["total_groups_processed"] += 1
            overall_stats["total_files_downloaded"] += stats["files_downloaded"]
            overall_stats["total_messages_scanned"] += stats["total_messages_scanned"]
        except Exception as e:
            logger.error(f"  Fatal error scraping {group_identifier}: {e}")
            overall_stats["groups"].append({
                "identifier": group_identifier,
                "error": str(e),
            })

        # Delay between groups
        delay = config.get("request_delay", 0.5)
        await asyncio.sleep(delay)

    # Save overall manifest
    overall_path = output_dir / "scraper_manifest.json"
    overall_stats["completed_at"] = datetime.now(timezone.utc).isoformat()

    with open(overall_path, "w", encoding="utf-8") as f:
        json.dump(overall_stats, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"\n{'='*60}")
    logger.info("SCRAPING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Groups processed:    {overall_stats['total_groups_processed']}")
    logger.info(f"Files downloaded:    {overall_stats['total_files_downloaded']}")
    logger.info(f"Messages scanned:    {overall_stats['total_messages_scanned']}")
    logger.info(f"Output directory:    {output_dir.resolve()}")
    logger.info(f"Manifest:            {overall_path}")
    logger.info(f"Completed at:        {overall_stats['completed_at']}")

    # Print per-group summary
    for g in overall_stats["groups"]:
        status = "OK" if not g.get("error") else f"ERROR: {g['error']}"
        logger.info(
            f"  {g.get('group', g['identifier']):30s} "
            f"{g.get('files_downloaded', 0):>4} files  "
            f"{g.get('total_messages_scanned', 0):>6} msgs  [{status}]"
        )

    return overall_stats


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Spooky2 preset files from Telegram groups",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with config file
  python3 telegram_scraper.py --config telegram_config.env

  # Dry run (list groups, don't download)
  python3 telegram_scraper.py --config telegram_config.env --dry-run

  # Override output directory
  python3 telegram_scraper.py --config telegram_config.env --output-dir ./my_presets

  # Test connectivity only
  python3 telegram_scraper.py --config telegram_config.env --test
        """,
    )

    parser.add_argument(
        "--config", "-c",
        default="telegram_config.env",
        help="Path to configuration file (default: telegram_config.env)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Override output directory",
    )
    parser.add_argument(
        "--group", "-g",
        action="append",
        help="Add a group to scrape (can be used multiple times, overrides config)",
    )
    parser.add_argument(
        "--max-messages", "-m",
        type=int,
        default=0,
        help="Max messages to scan per group (0 = unlimited)",
    )
    parser.add_argument(
        "--since", "-s",
        help="Start from date (ISO format, e.g. 2024-01-01 or 2024-01-01T00:00:00Z)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List identified groups without downloading",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test connectivity and group resolution only",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh without resuming previous progress",
    )

    args = parser.parse_args()

    # Load config
    if not os.path.exists(args.config):
        if args.config == "telegram_config.env":
            print(f"Config file not found: {args.config}")
            print(f"Copy telegram_config.example.env to {args.config} and fill in your credentials.")
            sys.exit(1)
        else:
            print(f"Config file not found: {args.config}")
            sys.exit(1)

    config = load_config(args.config)

    # Apply CLI overrides
    if args.output_dir:
        config["output_dir"] = args.output_dir
    if args.group:
        config["groups"] = args.group
    if args.max_messages:
        config["max_messages"] = args.max_messages
    if args.since:
        config["since"] = args.since
    if args.no_resume:
        config["resume"] = False
    if args.verbose:
        config["log_level"] = "DEBUG"

    # Setup logging
    logger = setup_logging(
        config["log_level"],
        config.get("log_file") if not args.dry_run and not args.test else None,
    )

    if args.dry_run:
        logger.info("Dry run mode - listing groups that would be scraped:")
        for g in config["groups"]:
            logger.info(f"  - {g}")
        logger.info(f"Output directory would be: {config['output_dir']}")
        sys.exit(0)

    if args.test:
        logger.info("Test mode - verifying connectivity and group resolution...")

        async def test_connectivity():
            client = await create_client(config)
            me = await client.get_me()

            if config.get("bot_token"):
                logger.info(f"Connected as bot: @{me.username}")
            else:
                logger.info(f"Connected as user: {me.first_name} (@{me.username})")

            for group_identifier in config["groups"]:
                peer = await resolve_peer(client, group_identifier)
                if peer:
                    info = await get_group_info(client, peer)
                    logger.info(f"  ✓ {group_identifier} -> {info['title']} ({info.get('participants_count', '?')} members)")
                else:
                    logger.error(f"  ✗ {group_identifier} -> COULD NOT RESOLVE")

            await client.disconnect()

        asyncio.run(test_connectivity())
        sys.exit(0)

    # Run the scraper
    stats = asyncio.run(run_scraper(config, logger))

    # Exit code based on results
    errors = [g for g in stats["groups"] if g.get("error")]
    if errors:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()