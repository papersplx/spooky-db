#!/usr/bin/env python3
"""Import Spooky2 preset data into Neon Postgres database."""
import json
import psycopg2
from psycopg2.extras import execute_batch

# Connection string from user - use environment variable
CONN_STRING = os.environ.get("NEON_CONN_STRING")
if not CONN_STRING:
    raise ValueError("NEON_CONN_STRING environment variable is required")

def main():
    # Connect to Neon
    print("Connecting to Neon...")
    conn = psycopg2.connect(CONN_STRING)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Create table
    print("Creating table...")
    cur.execute("""
        DROP TABLE IF EXISTS programs;
        CREATE TABLE programs (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            code TEXT,
            entry_type TEXT,
            loaded_programs TEXT,
            frequencies JSONB,
            preset_file TEXT,
            collection TEXT,
            mode TEXT,
            category TEXT,
            default_dwell NUMERIC
        );
        CREATE INDEX idx_name ON programs USING gin(to_tsvector('english', name));
        CREATE INDEX idx_description ON programs USING gin(to_tsvector('english', description));
        CREATE INDEX idx_collection ON programs(collection);
        CREATE INDEX idx_mode ON programs(mode);
        CREATE INDEX idx_entry_type ON programs(entry_type);
    """)
    
    # Load data
    print("Loading JSON data...")
    with open('data/presets/presets_all.json', 'r') as f:
        data = json.load(f)
    programs = data.get('programs', [])
    print(f"Found {len(programs)} programs")
    
    # Prepare data for batch insert
    batch = []
    for p in programs:
        batch.append((
            p['id'],
            p['name'],
            p.get('description', ''),
            p.get('code', ''),
            p.get('entry_type', ''),
            p.get('loaded_programs', ''),
            json.dumps(p.get('frequencies', [])),
            p.get('preset_file', ''),
            p.get('collection', ''),
            p.get('mode', ''),
            p.get('category', ''),
            p.get('default_dwell', None)
        ))
    
    # Insert in batches
    print("Inserting data...")
    execute_batch(cur, """
        INSERT INTO programs (id, name, description, code, entry_type, loaded_programs, frequencies, preset_file, collection, mode, category, default_dwell)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, batch, page_size=1000)
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM programs")
    count = cur.fetchone()[0]
    print(f"Successfully inserted {count} programs")
    
    cur.close()
    conn.close()
    print("Done!")

if __name__ == '__main__':
    main()
