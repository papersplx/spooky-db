#!/usr/bin/env python3
"""REST API for Spooky2 search using Neon Postgres."""
import logging
import subprocess
from fastapi import FastAPI, Query, HTTPException, Request
from pathlib import Path
import json
import os
from datetime import datetime, timezone
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("uvicorn")

app = FastAPI(title="Spooky2 Search API", version="1.0.0")

API_VERSION = "1.0.0"

# Path to local data directory for Telegram timestamps
DATA_DIR = Path(os.environ.get("DATA_DIR", "data/presets"))

# Neon connection — deferred until first database call
CONN_STRING = os.environ.get("NEON_CONN_STRING")

MIGRATION_SQL = """
DO $$
BEGIN
    -- Add source column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'programs' AND column_name = 'source'
    ) THEN
        ALTER TABLE programs ADD COLUMN source TEXT DEFAULT 'wine';
    END IF;
    -- Add tag column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'programs' AND column_name = 'tag'
    ) THEN
        ALTER TABLE programs ADD COLUMN tag TEXT;
    END IF;
    -- Add created_at column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'programs' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE programs ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
    -- Backfill source for existing rows
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'programs' AND column_name = 'source') THEN
        UPDATE programs SET source = 'wine' WHERE source IS NULL;
    END IF;
END $$;
"""

if CONN_STRING:
    try:
        _conn = psycopg.connect(CONN_STRING)
        with _conn.cursor() as _cur:
            _cur.execute(MIGRATION_SQL)
        _conn.commit()
        _conn.close()
        # Auto-import data if table is empty (first run)
        import threading
        def run_import():
            try:
                logger.info("Checking if data import is needed...")
                conn2 = psycopg.connect(CONN_STRING)
                with conn2.cursor() as cur2:
                    cur2.execute("SELECT COUNT(*) FROM programs")
                    count = cur2.fetchone()[0]
                conn2.close()
                if count == 0:
                    logger.info("No programs found — running import_to_neon.py...")
                    result = subprocess.run([sys.executable, "import_to_neon.py"], capture_output=True, text=True, cwd=Path(__file__).parent)
                    if result.returncode == 0:
                        logger.info("Import completed")
                    else:
                        logger.error(f"Import failed: {result.stderr}")
                else:
                    logger.info(f"Database already has {count} programs — skipping import")
            except Exception as e:
                logger.error(f"Auto-import error: {e}")
        threading.Thread(target=run_import, daemon=True).start()
    except Exception as _e:
        import warnings
        warnings.warn(f"Migration failed: {_e}")

if not CONN_STRING:
    import warnings
    warnings.warn(
        "NEON_CONN_STRING not set. Database endpoints (/search, /program, /collections) "
        "will return errors. Static endpoints (/telegram-updates, /health) still work."
    )


@app.get("/")
def read_root():
    return {
        "message": "Spooky2 Frequency Search API",
        "version": API_VERSION,
        "frontend": "https://papersplx.github.io/spooky-db/",
        "endpoints": {
            "search": "/search?q=lung&limit=100",
            "program": "/program?id=<uuid>",
            "collections": "/collections",
            "telegram-updates": "/telegram-updates",
            "health": "/health"
        }
    }


# CORS — allow frontend origins; disable credentials when using wildcard
@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "https://papersplx.github.io"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.get("/search")
def search(
    q: str = Query(default=""),
    mode: list[str] = Query(default=[]),
    collection: list[str] = Query(default=[]),
    category: list[str] = Query(default=[]),
    source: list[str] = Query(default=[]),
    tag: list[str] = Query(default=[]),
    limit: int = Query(default=100),
    offset: int = Query(default=0)
):
    conn = psycopg.connect(CONN_STRING, row_factory=dict_row)
    try:
        where = []
        params = []

        if q:
            where.append("to_tsvector('english', name || ' ' || COALESCE(description, '')) @@ plainto_tsquery('english', %s)")
            params.append(q)

        if mode:
            where.append("mode = ANY(%s)")
            params.append(mode)

        if collection:
            where.append("collection = ANY(%s)")
            params.append(collection)

        if category:
            where.append("category = ANY(%s)")
            params.append(category)

        if source:
            where.append("source = ANY(%s)")
            params.append(source)

        if tag:
            where.append("tag = ANY(%s)")
            params.append(tag)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT COUNT(*) as total
                FROM programs
                {where_clause}
            """, params)
            total = cur.fetchone()['total']

            cur.execute(f"""
                SELECT id, name, description, collection, mode, entry_type, source, tag
                FROM programs
                {where_clause}
                ORDER BY name
                LIMIT %s OFFSET %s
            """, [*params, limit, offset])
            results = cur.fetchall()
            return {"results": results, "total": total}
    finally:
        conn.close()

@app.get("/program")
def get_program(id: str):
    conn = psycopg.connect(CONN_STRING, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM programs WHERE id = %s LIMIT 1", (id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Program not found")
            return result
    finally:
        conn.close()

@app.get("/collections")
def get_collections():
    conn = psycopg.connect(CONN_STRING, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT collection, mode, COUNT(*) as count
                FROM programs
                GROUP BY collection, mode
                ORDER BY collection
            """)
            collections = cur.fetchall()

            sources = []
            try:
                cur.execute("""
                    SELECT source, tag, COUNT(*) as count
                    FROM programs
                    WHERE source IS NOT NULL AND source != 'wine'
                    GROUP BY source, tag
                    ORDER BY source, tag
                """)
                sources = cur.fetchall()
            except Exception:
                sources = []

            return {"collections": collections, "sources": sources}
    finally:
        conn.close()

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/telegram-updates")
def telegram_updates():
    """Return last-updated timestamps for Telegram groups and database .exe files."""
    result = {}

    # Telegram group timestamps
    timestamp_path = DATA_DIR / "telegram_group_timestamps.json"
    if timestamp_path.exists():
        try:
            with open(timestamp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for group_slug, info in data.items():
                if isinstance(info, str):
                    result[group_slug] = info
                elif isinstance(info, dict):
                    result[group_slug] = info.get("last_updated")
        except Exception:
            pass

    # Also check for manifest files in each group directory
    telegram_dir = DATA_DIR / "telegram_raw"
    if telegram_dir.exists():
        for group_dir in telegram_dir.iterdir():
            if not group_dir.is_dir():
                continue
            manifest_path = group_dir / "postprocess_manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    group_name = group_dir.name
                    if group_name not in result or result[group_name] is None:
                        result[group_name] = manifest.get("completed_at")
                except Exception:
                    pass

    # Fall back to progress.json timestamps if no other source
    for group_slug in list(result.keys()):
        if result[group_slug] is None:
            progress_path = DATA_DIR / "telegram_raw" / group_slug / "progress.json"
            if progress_path.exists():
                try:
                    mtime = progress_path.stat().st_mtime
                    result[group_slug] = datetime.fromtimestamp(
                        mtime, tz=timezone.utc
                    ).isoformat()
                except Exception:
                    pass

    # Database .exe file timestamps - loaded from repo (versioned with code)
    db_timestamp_path = Path(__file__).parent / "data" / "presets" / "database_timestamps.json"
    if db_timestamp_path.exists():
        try:
            with open(db_timestamp_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)
            if db_data and isinstance(db_data, dict):
                logger.info(f"Loaded database timestamps: {list(db_data.keys())}")
                result.update(db_data)
        except Exception as e:
            logger.error(f"Failed to load database timestamps: {e}")

    return result


@app.get("/telegram-tags")
def telegram_tags():
    """Return aggregated counts by source and tag."""
    conn = psycopg.connect(CONN_STRING, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, tag, COUNT(*) as count
                FROM programs
                WHERE source IS NOT NULL
                GROUP BY source, tag
                ORDER BY source, tag
            """)
            return cur.fetchall()
    finally:
        conn.close()


@app.post("/reimport")
def reimport_data(request: Request):
    """Re-import presets_all.json to Neon database (admin only)."""
    token = request.query_params.get("token")
    if not token or token != os.environ.get("REIMPORT_TOKEN", "reimport-secret"):
        raise HTTPException(status_code=403, detail="Invalid or missing token")
    
    try:
        script_path = Path(__file__).parent / "import_to_neon.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            return {"status": "ok", "message": "Reimport completed", "output": result.stdout}
        else:
            return {
                "status": "error",
                "message": "Reimport failed",
                "stderr": result.stderr,
                "stdout": result.stdout,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reimport error: {e}")
