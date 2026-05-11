#!/usr/bin/env python3
"""Import Spooky2 preset data from JSON into Neon Postgres."""

import json
import os
import sys
from datetime import datetime

import psycopg
from psycopg.rows import dict_row


DATA_DIR = os.environ.get("DATA_DIR", "data/presets")
CONN_STRING = os.environ.get("NEON_CONN_STRING")
PRESETS_FILE = os.path.join(DATA_DIR, "presets_all.json")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS programs (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    code TEXT DEFAULT '',
    frequencies JSONB DEFAULT '[]',
    preset_file TEXT,
    collection TEXT,
    mode TEXT DEFAULT 'Other',
    category TEXT,
    default_dwell INTEGER,
    entry_type TEXT DEFAULT 'program',
    loaded_programs TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_programs_name ON programs (name);",
    "CREATE INDEX IF NOT EXISTS idx_programs_mode ON programs (mode);",
    "CREATE INDEX IF NOT EXISTS idx_programs_collection ON programs (collection);",
    "CREATE INDEX IF NOT EXISTS idx_programs_category ON programs (category);",
    "CREATE INDEX IF NOT EXISTS idx_programs_entry_type ON programs (entry_type);",
    "CREATE INDEX IF NOT EXISTS idx_programs_gin ON programs USING GIN (frequencies);",
    "CREATE INDEX IF NOT EXISTS idx_programs_tsvector ON programs USING GIN (to_tsvector('english', name || ' ' || COALESCE(description, '')));",
]


def get_connection():
    if not CONN_STRING:
        print("ERROR: NEON_CONN_STRING environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return psycopg.connect(CONN_STRING, row_factory=dict_row)


def setup_database(conn):
    """Create table and indexes if they don't exist."""
    print("Setting up database schema...")
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEXES_SQL:
            cur.execute(idx_sql)
    conn.commit()
    print("  Schema ready.")


def clear_existing_data(conn):
    """Delete all existing rows."""
    print("Clearing existing data...")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM programs")
    conn.commit()
    print("  Cleared.")


def import_data(conn, presets_file):
    """Import programs from JSON file."""
    if not os.path.exists(presets_file):
        print(f"ERROR: Presets file not found: {presets_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {presets_file}...")
    with open(presets_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    programs = data.get("programs", [])
    total = len(programs)
    print(f"  Found {total} programs to import.")

    inserted = 0
    errors = 0

    with conn.cursor() as cur:
        for i, prog in enumerate(programs):
            try:
                cur.execute(
                    """
                    INSERT INTO programs (
                        id, name, description, code, frequencies,
                        preset_file, collection, mode, category,
                        default_dwell, entry_type, loaded_programs
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        code = EXCLUDED.code,
                        frequencies = EXCLUDED.frequencies,
                        preset_file = EXCLUDED.preset_file,
                        collection = EXCLUDED.collection,
                        mode = EXCLUDED.mode,
                        category = EXCLUDED.category,
                        default_dwell = EXCLUDED.default_dwell,
                        entry_type = EXCLUDED.entry_type,
                        loaded_programs = EXCLUDED.loaded_programs,
                        created_at = NOW()
                    """,
                    (
                        prog["id"],
                        prog.get("name", ""),
                        prog.get("description"),
                        prog.get("code", ""),
                        json.dumps(prog.get("frequencies", [])),
                        prog.get("preset_file"),
                        prog.get("collection"),
                        prog.get("mode", "Other"),
                        prog.get("category"),
                        prog.get("default_dwell"),
                        prog.get("entry_type", "program"),
                        prog.get("loaded_programs"),
                    ),
                )
                inserted += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Error on program {i + 1}/{total} (id={prog.get('id', '?')}): {e}", file=sys.stderr)

            if (i + 1) % 5000 == 0:
                conn.commit()
                print(f"  Progress: {i + 1}/{total} ({inserted} inserted, {errors} errors)")

    conn.commit()
    print(f"\nImport complete: {inserted} inserted, {errors} errors out of {total} total.")


def verify_import(conn):
    """Run basic verification queries."""
    print("\nVerifying import...")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM programs")
        total = cur.fetchone()["total"]
        print(f"  Total programs in DB: {total}")

        cur.execute("SELECT COUNT(*) as cnt FROM programs WHERE category IS NOT NULL")
        with_cat = cur.fetchone()["cnt"]
        print(f"  With category: {with_cat}")

        cur.execute("SELECT mode, COUNT(*) as cnt FROM programs GROUP BY mode ORDER BY cnt DESC LIMIT 5")
        print("  Mode distribution (top 5):")
        for row in cur.fetchall():
            print(f"    {row['mode']}: {row['cnt']}")

        cur.execute("SELECT category, COUNT(*) as cnt FROM programs WHERE category IS NOT NULL GROUP BY category ORDER BY cnt DESC LIMIT 10")
        print("  Category distribution (top 10):")
        for row in cur.fetchall():
            print(f"    {row['category']}: {row['cnt']}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import Spooky2 preset JSON into Neon Postgres")
    parser.add_argument("--file", "-f", type=str, default=PRESETS_FILE, help="Path to presets JSON file")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before import")
    parser.add_argument("--skip-setup", action="store_true", help="Skip table/index creation")
    parser.add_argument("--verify", action="store_true", help="Run verification after import")

    args = parser.parse_args()

    conn = get_connection()
    try:
        if not args.skip_setup:
            setup_database(conn)

        if args.clear:
            clear_existing_data(conn)

        import_data(conn, args.file)

        if args.verify:
            verify_import(conn)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())